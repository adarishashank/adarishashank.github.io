/* MiniSQL: a small Spark-SQL-flavoured engine over in-memory tables.
 *
 *   SELECT [DISTINCT] expr [AS alias], ... | *
 *   [FROM table] [WHERE expr] [GROUP BY expr, ...] [HAVING expr]
 *   [ORDER BY expr|alias|ordinal [ASC|DESC] [NULLS FIRST|LAST], ...] [LIMIT n [OFFSET m]]
 *   SHOW TABLES · DESCRIBE [TABLE] t · HELP
 *
 * Tables: { name: { description, columns: [{name, type}], rows: [[...], ...] } }
 * No dependencies; works in browsers and in plain JS engines (used by the tests).
 */
(function (root) {
  "use strict";

  var MAX_ROWS = 1000;

  function SqlError(code, msg) {
    var e = new Error("[" + code + "] " + msg);
    e.sqlCode = code;
    return e;
  }

  function lineCol(src, pos) {
    var before = src.slice(0, pos).split("\n");
    return "(line " + before.length + ", pos " + before[before.length - 1].length + ")";
  }

  // ------------------------------------------------------------------ tokenizer
  var KW = {};
  ("SELECT DISTINCT FROM WHERE GROUP BY HAVING ORDER ASC DESC LIMIT OFFSET AND OR NOT LIKE ILIKE IN IS " +
   "NULL AS TRUE FALSE BETWEEN SHOW TABLES DESCRIBE TABLE HELP CASE WHEN THEN ELSE END NULLS FIRST LAST")
    .split(" ").forEach(function (k) { KW[k] = true; });

  function tokenize(src) {
    var out = [], i = 0, n = src.length;
    while (i < n) {
      var c = src[i], start = i, m;
      if (/\s/.test(c)) { i++; continue; }
      if (c === "-" && src[i + 1] === "-") { while (i < n && src[i] !== "\n") i++; continue; }
      if (c === "/" && src[i + 1] === "*") { var j = src.indexOf("*/", i + 2); i = j < 0 ? n : j + 2; continue; }
      if (c === "'") {
        var s = "";
        i++;
        for (;;) {
          if (i >= n) throw SqlError("UNCLOSED_LITERAL", "The string starting at " + lineCol(src, start) + " is never closed.");
          if (src[i] === "'") {
            if (src[i + 1] === "'") { s += "'"; i += 2; continue; }
            i++;
            break;
          }
          s += src[i++];
        }
        out.push({ t: "str", v: s, pos: start, end: i });
        continue;
      }
      if (c === '"' || c === "`") {
        var q = src.indexOf(c, i + 1);
        if (q < 0) throw SqlError("UNCLOSED_IDENTIFIER", "The quoted identifier starting at " + lineCol(src, start) + " is never closed.");
        out.push({ t: "id", v: src.slice(i + 1, q), pos: start, end: q + 1 });
        i = q + 1;
        continue;
      }
      if ((m = /^(\d+\.?\d*|\.\d+)(e[+-]?\d+)?/i.exec(src.slice(i)))) {
        out.push({ t: "num", v: Number(m[0]), pos: start, end: i + m[0].length });
        i += m[0].length;
        continue;
      }
      if ((m = /^[A-Za-z_][A-Za-z0-9_]*/.exec(src.slice(i)))) {
        var up = m[0].toUpperCase();
        out.push(KW[up] ? { t: "kw", v: up, pos: start, end: i + m[0].length }
                        : { t: "id", v: m[0], pos: start, end: i + m[0].length });
        i += m[0].length;
        continue;
      }
      var two = src.slice(i, i + 2);
      if (two === "<=" || two === ">=" || two === "<>" || two === "!=" || two === "||" || two === "==") {
        out.push({ t: "op", v: two === "==" ? "=" : two === "<>" ? "!=" : two, pos: start, end: i + 2 });
        i += 2;
        continue;
      }
      if ("=<>+-*/%".indexOf(c) >= 0) { out.push({ t: "op", v: c, pos: start, end: i + 1 }); i++; continue; }
      if ("(),;.".indexOf(c) >= 0) { out.push({ t: "p", v: c, pos: start, end: i + 1 }); i++; continue; }
      throw SqlError("PARSE_SYNTAX_ERROR", "Unexpected character '" + c + "' " + lineCol(src, i) + ".");
    }
    out.push({ t: "eof", v: "", pos: n, end: n });
    return out;
  }

  // ------------------------------------------------------------------ functions
  var AGG = { COUNT: 1, SUM: 1, AVG: 1, MIN: 1, MAX: 1 };

  function str(v) { return v == null ? null : String(v); }
  function nullIfAny(fn) {
    return function (a) { for (var i = 0; i < a.length; i++) if (a[i] == null) return null; return fn(a); };
  }
  function coalesce(a) { for (var i = 0; i < a.length; i++) if (a[i] != null) return a[i]; return null; }

  var SCALAR = {
    UPPER: nullIfAny(function (a) { return str(a[0]).toUpperCase(); }),
    LOWER: nullIfAny(function (a) { return str(a[0]).toLowerCase(); }),
    LENGTH: nullIfAny(function (a) { return str(a[0]).length; }),
    TRIM: nullIfAny(function (a) { return str(a[0]).trim(); }),
    ABS: nullIfAny(function (a) { return Math.abs(Number(a[0])); }),
    ROUND: function (a) {
      if (a[0] == null) return null;
      var p = Math.pow(10, a[1] == null ? 0 : Number(a[1]));
      return Math.round(Number(a[0]) * p) / p;
    },
    COALESCE: coalesce, IFNULL: coalesce, NVL: coalesce,
    CONCAT: nullIfAny(function (a) { return a.map(String).join(""); }),
    SUBSTR: function (a) {
      if (a[0] == null) return null;
      var s = str(a[0]), pos = Number(a[1] == null ? 1 : a[1]);
      var from = pos > 0 ? pos - 1 : Math.max(0, s.length + pos);
      return a[2] == null ? s.slice(from) : s.slice(from, from + Number(a[2]));
    },
    YEAR: nullIfAny(function (a) { return Number(str(a[0]).slice(0, 4)); }),
    MONTH: nullIfAny(function (a) { return Number(str(a[0]).slice(5, 7)); }),
    CURRENT_DATE: function () { return new Date().toISOString().slice(0, 10); },
    DATEDIFF: nullIfAny(function (a) {
      return Math.round((Date.parse(str(a[0]).slice(0, 10)) - Date.parse(str(a[1]).slice(0, 10))) / 86400000);
    }),
  };
  SCALAR.SUBSTRING = SCALAR.SUBSTR;

  // ------------------------------------------------------------------ parser
  function Parser(src) { this.src = src; this.toks = tokenize(src); this.i = 0; }
  var P = Parser.prototype;
  P.peek = function (k) { return this.toks[Math.min(this.i + (k || 0), this.toks.length - 1)]; };
  P.next = function () { return this.toks[this.i++]; };
  P.isKw = function (v, k) { var t = this.peek(k); return t.t === "kw" && t.v === v; };
  P.isP = function (v) { var t = this.peek(); return t.t === "p" && t.v === v; };
  P.isOp = function (v) { var t = this.peek(); return t.t === "op" && t.v === v; };
  P.acceptKw = function (v) { if (this.isKw(v)) { this.i++; return true; } return false; };
  P.acceptP = function (v) { if (this.isP(v)) { this.i++; return true; } return false; };
  P.expectKw = function (v) { if (!this.acceptKw(v)) this.fail("expected " + v); };
  P.expectP = function (v) { if (!this.acceptP(v)) this.fail("expected '" + v + "'"); };
  P.fail = function (hint) {
    var t = this.peek();
    var near = t.t === "eof" ? "end of input" : "'" + this.src.slice(t.pos, t.end) + "'";
    throw SqlError("PARSE_SYNTAX_ERROR", "Syntax error at or near " + near + (hint ? ": " + hint : "") + ". " + lineCol(this.src, t.pos));
  };
  P.ident = function (what) {
    var t = this.peek();
    if (t.t === "id") { this.i++; return t.v; }
    this.fail("expected " + (what || "an identifier"));
  };
  P.tableName = function () {
    var parts = [this.ident("a table name")];
    while (this.acceptP(".")) parts.push(this.ident("a table name"));
    return parts.join(".");
  };

  P.statement = function () {
    var st, first = this.peek();
    if (first.t === "id" && /^(DROP|DELETE|INSERT|UPDATE|CREATE|ALTER|TRUNCATE|MERGE|GRANT|REVOKE)$/i.test(first.v)) {
      throw SqlError("READ_ONLY_CATALOG", "Nice try. The shashank catalog is read-only for visitors; only the pipeline writes to it.");
    }
    if (this.acceptKw("SHOW")) { this.expectKw("TABLES"); st = { type: "show" }; }
    else if (this.isKw("DESCRIBE") || this.isKw("DESC")) { this.i++; this.acceptKw("TABLE"); st = { type: "describe", table: this.tableName() }; }
    else if (this.acceptKw("HELP")) st = { type: "help" };
    else if (this.isKw("SELECT")) st = this.select();
    else this.fail("statements start with SELECT, SHOW TABLES, DESCRIBE or HELP");
    this.acceptP(";");
    if (this.peek().t !== "eof") this.fail("one statement at a time");
    return st;
  };

  P.select = function () {
    this.expectKw("SELECT");
    var st = { type: "select", distinct: this.acceptKw("DISTINCT"), items: [], from: null, where: null,
               groupBy: [], having: null, orderBy: [], limit: null, offset: 0 };
    do {
      if (this.isOp("*")) { this.i++; st.items.push({ star: true }); continue; }
      var start = this.peek().pos, expr = this.expr();
      var text = this.src.slice(start, this.toks[this.i - 1].end).replace(/\s+/g, " ").trim();
      var alias = null;
      if (this.acceptKw("AS")) alias = this.ident("an alias");
      else if (this.peek().t === "id") alias = this.next().v;
      st.items.push({ expr: expr, alias: alias, text: text });
    } while (this.acceptP(","));

    if (this.acceptKw("FROM")) {
      st.from = this.tableName();
      if (this.acceptKw("AS")) this.ident("an alias");
      else if (this.peek().t === "id") this.i++;
    }
    if (this.acceptKw("WHERE")) st.where = this.expr();
    if (this.acceptKw("GROUP")) { this.expectKw("BY"); st.groupBy = this.exprList(); }
    if (this.acceptKw("HAVING")) st.having = this.expr();
    if (this.acceptKw("ORDER")) {
      this.expectKw("BY");
      do {
        var o = { expr: this.expr(), desc: false, nullsFirst: null };
        if (this.acceptKw("DESC")) o.desc = true; else this.acceptKw("ASC");
        if (this.acceptKw("NULLS")) {
          if (this.acceptKw("FIRST")) o.nullsFirst = true; else { this.expectKw("LAST"); o.nullsFirst = false; }
        }
        st.orderBy.push(o);
      } while (this.acceptP(","));
    }
    if (this.acceptKw("LIMIT")) {
      st.limit = this.intLit();
      if (this.acceptKw("OFFSET")) st.offset = this.intLit();
    }
    return st;
  };

  P.intLit = function () {
    var t = this.peek();
    if (t.t !== "num" || t.v < 0 || Math.floor(t.v) !== t.v) this.fail("expected a non-negative integer");
    this.i++;
    return t.v;
  };
  P.exprList = function () { var l = []; do { l.push(this.expr()); } while (this.acceptP(",")); return l; };

  P.expr = function () { return this.or(); };
  P.or = function () { var l = this.and(); while (this.acceptKw("OR")) l = { k: "or", l: l, r: this.and() }; return l; };
  P.and = function () { var l = this.not(); while (this.acceptKw("AND")) l = { k: "and", l: l, r: this.not() }; return l; };
  P.not = function () { return this.acceptKw("NOT") ? { k: "not", e: this.not() } : this.cmp(); };
  P.cmp = function () {
    var l = this.add(), t = this.peek();
    if (t.t === "op" && /^(=|!=|<|>|<=|>=)$/.test(t.v)) { this.i++; return { k: "cmp", op: t.v, l: l, r: this.add() }; }
    var neg = false;
    if (this.isKw("NOT") && (this.isKw("LIKE", 1) || this.isKw("ILIKE", 1) || this.isKw("IN", 1) || this.isKw("BETWEEN", 1))) { this.i++; neg = true; }
    var node = null;
    if (this.acceptKw("LIKE")) node = { k: "like", l: l, r: this.add(), ci: false };
    else if (this.acceptKw("ILIKE")) node = { k: "like", l: l, r: this.add(), ci: true };
    else if (this.acceptKw("IN")) { this.expectP("("); node = { k: "in", l: l, list: this.exprList() }; this.expectP(")"); }
    else if (this.acceptKw("BETWEEN")) { var lo = this.add(); this.expectKw("AND"); node = { k: "between", l: l, lo: lo, hi: this.add() }; }
    else if (this.acceptKw("IS")) { var isNot = this.acceptKw("NOT"); this.expectKw("NULL"); return { k: "isnull", l: l, neg: isNot }; }
    if (!node) return l;
    return neg ? { k: "not", e: node } : node;
  };
  P.add = function () {
    var l = this.mul();
    for (;;) {
      var t = this.peek();
      if (t.t === "op" && (t.v === "+" || t.v === "-" || t.v === "||")) { this.i++; l = { k: "bin", op: t.v, l: l, r: this.mul() }; }
      else return l;
    }
  };
  P.mul = function () {
    var l = this.unary();
    for (;;) {
      var t = this.peek();
      if (t.t === "op" && (t.v === "*" || t.v === "/" || t.v === "%")) { this.i++; l = { k: "bin", op: t.v, l: l, r: this.unary() }; }
      else return l;
    }
  };
  P.unary = function () {
    if (this.isOp("-")) { this.i++; return { k: "neg", e: this.unary() }; }
    if (this.isOp("+")) { this.i++; return this.unary(); }
    return this.primary();
  };
  P.primary = function () {
    var t = this.peek();
    if (t.t === "num" || t.t === "str") { this.i++; return { k: "lit", v: t.v }; }
    if (t.t === "kw") {
      if (t.v === "NULL") { this.i++; return { k: "lit", v: null }; }
      if (t.v === "TRUE" || t.v === "FALSE") { this.i++; return { k: "lit", v: t.v === "TRUE" }; }
      if (t.v === "CASE") { this.i++; return this.caseExpr(); }
    }
    if (this.acceptP("(")) { var e = this.expr(); this.expectP(")"); return e; }
    if (t.t === "id") {
      this.i++;
      if (this.isP("(")) return this.callExpr(t.v);
      if (this.acceptP(".")) {
        if (this.isOp("*")) this.fail("qualified star is not supported, use *");
        return { k: "col", name: this.ident("a column name") };
      }
      return { k: "col", name: t.v };
    }
    this.fail(t.t === "eof" ? "expression expected" : "");
  };
  P.callExpr = function (name) {
    var fn = name.toUpperCase(), node = { args: [], star: false, distinct: false };
    this.expectP("(");
    if (this.isOp("*")) { this.i++; node.star = true; }
    else if (!this.isP(")")) { node.distinct = this.acceptKw("DISTINCT"); node.args = this.exprList(); }
    this.expectP(")");
    if (AGG[fn]) {
      if (node.star && fn !== "COUNT") throw SqlError("INVALID_FUNCTION_ARGS", fn + "(*) is not valid; only COUNT(*) is.");
      if (!node.star && node.args.length !== 1) throw SqlError("WRONG_NUM_ARGS", fn + " takes exactly one argument.");
      return { k: "agg", fn: fn, args: node.args, star: node.star, distinct: node.distinct };
    }
    if (!SCALAR[fn]) {
      throw SqlError("UNRESOLVED_ROUTINE", "Cannot resolve function `" + name + "`. Supported: " +
        Object.keys(AGG).concat(Object.keys(SCALAR)).join(", ") + ".");
    }
    if (node.star) this.fail("* is only valid inside COUNT");
    return { k: "fn", fn: fn, args: node.args };
  };
  P.caseExpr = function () {
    var node = { k: "case", operand: null, whens: [], other: null };
    if (!this.isKw("WHEN")) node.operand = this.expr();
    while (this.acceptKw("WHEN")) {
      var w = this.expr();
      this.expectKw("THEN");
      node.whens.push([w, this.expr()]);
    }
    if (!node.whens.length) this.fail("CASE needs at least one WHEN");
    if (this.acceptKw("ELSE")) node.other = this.expr();
    this.expectKw("END");
    return node;
  };

  // ------------------------------------------------------------------ evaluation
  function isNum(v) { return typeof v === "number" || typeof v === "boolean"; }
  function compare(a, b) {
    if (isNum(a) && isNum(b)) return Number(a) - Number(b);
    if (isNum(a) && b !== "" && !isNaN(Number(b))) return Number(a) - Number(b);
    if (isNum(b) && a !== "" && !isNaN(Number(a))) return Number(a) - Number(b);
    var x = String(a), y = String(b);
    return x < y ? -1 : x > y ? 1 : 0;
  }
  function truthy(v) { return v === true || (typeof v === "number" && v !== 0); }
  var likeCache = {};
  function likeRe(pattern, ci) {
    var key = (ci ? "i:" : "s:") + pattern;
    if (!likeCache[key]) {
      var body = String(pattern).replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/%/g, ".*").replace(/_/g, ".");
      likeCache[key] = new RegExp("^" + body + "$", ci ? "is" : "s");
    }
    return likeCache[key];
  }

  function evaluate(n, ctx) {
    var l, r, i, v;
    switch (n.k) {
      case "lit": return n.v;
      case "col": return ctx.col(n.name);
      case "agg": return ctx.agg(n);
      case "fn": return SCALAR[n.fn](n.args.map(function (a) { return evaluate(a, ctx); }));
      case "neg": v = evaluate(n.e, ctx); return v == null ? null : -Number(v);
      case "bin":
        l = evaluate(n.l, ctx); r = evaluate(n.r, ctx);
        if (l == null || r == null) return null;
        if (n.op === "||") return String(l) + String(r);
        var a = Number(l), b = Number(r);
        if (isNaN(a) || isNaN(b)) throw SqlError("DATATYPE_MISMATCH", "Cannot apply '" + n.op + "' to a non-numeric value. Use || to concatenate strings.");
        switch (n.op) {
          case "+": return a + b;
          case "-": return a - b;
          case "*": return a * b;
          case "/": return b === 0 ? null : a / b;
          case "%": return b === 0 ? null : a % b;
        }
        return null;
      case "cmp":
        l = evaluate(n.l, ctx); r = evaluate(n.r, ctx);
        if (l == null || r == null) return null;
        var c = compare(l, r);
        switch (n.op) {
          case "=": return c === 0;
          case "!=": return c !== 0;
          case "<": return c < 0;
          case ">": return c > 0;
          case "<=": return c <= 0;
          case ">=": return c >= 0;
        }
        return null;
      case "like":
        l = evaluate(n.l, ctx); r = evaluate(n.r, ctx);
        return l == null || r == null ? null : likeRe(r, n.ci).test(String(l));
      case "in":
        l = evaluate(n.l, ctx);
        if (l == null) return null;
        var sawNull = false;
        for (i = 0; i < n.list.length; i++) {
          v = evaluate(n.list[i], ctx);
          if (v == null) sawNull = true;
          else if (compare(l, v) === 0) return true;
        }
        return sawNull ? null : false;
      case "between":
        l = evaluate(n.l, ctx);
        var lo = evaluate(n.lo, ctx), hi = evaluate(n.hi, ctx);
        if (l == null || lo == null || hi == null) return null;
        return compare(l, lo) >= 0 && compare(l, hi) <= 0;
      case "isnull":
        v = evaluate(n.l, ctx);
        return n.neg ? v != null : v == null;
      case "not":
        v = evaluate(n.e, ctx);
        return v == null ? null : !truthy(v);
      case "and":
        l = evaluate(n.l, ctx);
        if (l != null && !truthy(l)) return false;
        r = evaluate(n.r, ctx);
        if (r != null && !truthy(r)) return false;
        return l == null || r == null ? null : true;
      case "or":
        l = evaluate(n.l, ctx);
        if (truthy(l)) return true;
        r = evaluate(n.r, ctx);
        if (truthy(r)) return true;
        return l == null || r == null ? null : false;
      case "case":
        var base = n.operand ? evaluate(n.operand, ctx) : undefined;
        for (i = 0; i < n.whens.length; i++) {
          var w = evaluate(n.whens[i][0], ctx);
          if (n.operand ? (base != null && w != null && compare(base, w) === 0) : truthy(w)) return evaluate(n.whens[i][1], ctx);
        }
        return n.other ? evaluate(n.other, ctx) : null;
    }
    throw SqlError("INTERNAL_ERROR", "unknown node " + n.k);
  }

  function hasAgg(n) {
    if (!n || typeof n !== "object") return false;
    if (n.k === "agg") return true;
    for (var key in n) {
      if (key === "k") continue;
      var v = n[key];
      if (Array.isArray(v)) { for (var i = 0; i < v.length; i++) if (hasAgg(Array.isArray(v[i]) ? { k: "x", a: v[i] } : v[i])) return true; }
      else if (v && typeof v === "object" && hasAgg(v)) return true;
    }
    return false;
  }

  function aggregate(n, rows, mk) {
    if (n.star) return rows.length;
    var vals = [];
    for (var i = 0; i < rows.length; i++) {
      var v = evaluate(n.args[0], mk(rows[i]));
      if (v != null) vals.push(v);
    }
    if (n.distinct) {
      var seen = {};
      vals = vals.filter(function (x) { var k = typeof x + ":" + x; if (seen[k]) return false; seen[k] = true; return true; });
    }
    switch (n.fn) {
      case "COUNT": return vals.length;
      case "SUM": return vals.length ? vals.reduce(function (s, x) { return s + Number(x); }, 0) : null;
      case "AVG": return vals.length ? vals.reduce(function (s, x) { return s + Number(x); }, 0) / vals.length : null;
      case "MIN": return vals.length ? vals.reduce(function (m, x) { return compare(x, m) < 0 ? x : m; }) : null;
      case "MAX": return vals.length ? vals.reduce(function (m, x) { return compare(x, m) > 0 ? x : m; }) : null;
    }
    return null;
  }

  function suggest(name, options) {
    var lower = name.toLowerCase();
    var ranked = options.slice().sort(function (a, b) {
      return score(b) - score(a);
      function score(o) {
        var x = o.toLowerCase(), s = 0;
        if (x.indexOf(lower) >= 0 || lower.indexOf(x) >= 0) s += 10;
        for (var i = 0; i < Math.min(x.length, lower.length) && x[i] === lower[i]; i++) s++;
        return s;
      }
    });
    return ranked.slice(0, 5).map(function (o) { return "`" + o + "`"; }).join(", ");
  }

  // ------------------------------------------------------------------ execution
  var HELP = [
    "MiniSQL: a small Spark SQL dialect, running in your browser.",
    "",
    "  SHOW TABLES",
    "  DESCRIBE <table>",
    "  SELECT [DISTINCT] <expr> [AS alias], ... | *",
    "    FROM <table> [WHERE <cond>]",
    "    [GROUP BY <expr>, ...] [HAVING <cond>]",
    "    [ORDER BY <expr|alias|n> [ASC|DESC] [NULLS FIRST|LAST], ...]",
    "    [LIMIT n [OFFSET m]]",
    "",
    "Operators   = != <> < > <= >=  AND OR NOT  + - * / %  ||",
    "            [NOT] LIKE / ILIKE ('%' and '_')  [NOT] IN (...)  [NOT] BETWEEN a AND b  IS [NOT] NULL",
    "            CASE WHEN ... THEN ... ELSE ... END",
    "Aggregates  COUNT(*) COUNT([DISTINCT] x) SUM AVG MIN MAX",
    "Functions   " + Object.keys(SCALAR).join(" "),
    "",
    "Try:  SELECT schema, COUNT(*) AS n FROM skills GROUP BY schema ORDER BY n DESC",
  ].join("\n");

  function inferType(values) {
    var t = null;
    for (var i = 0; i < values.length; i++) {
      var v = values[i];
      if (v == null) continue;
      var vt = typeof v === "number" ? (Math.floor(v) === v ? "bigint" : "double") : typeof v === "boolean" ? "boolean" : "string";
      if (t && t !== vt) return t === "bigint" && vt === "double" || t === "double" && vt === "bigint" ? "double" : "string";
      t = vt;
    }
    return t || "string";
  }

  function execute(sql, tables) {
    var st = new Parser(sql).statement();
    var names = Object.keys(tables).sort();

    if (st.type === "help") return { kind: "text", text: HELP };
    if (st.type === "show") {
      return {
        kind: "table", columns: ["table", "rows", "description"], types: ["string", "bigint", "string"],
        rows: names.map(function (n) { return [n, tables[n].rows.length, tables[n].description || null]; }),
      };
    }

    function lookup(name) {
      var key = name.toLowerCase().replace(/^(shashank\.)?(default\.)?/, "");
      for (var i = 0; i < names.length; i++) if (names[i].toLowerCase() === key) return tables[names[i]];
      throw SqlError("TABLE_OR_VIEW_NOT_FOUND", "The table or view `" + name + "` cannot be found. Did you mean one of: " + suggest(name, names) + "?");
    }

    if (st.type === "describe") {
      var dt = lookup(st.table);
      return {
        kind: "table", columns: ["col_name", "data_type"], types: ["string", "string"],
        rows: dt.columns.map(function (c) { return [c.name, c.type]; }), note: dt.description,
      };
    }

    // ---- SELECT
    var table = st.from ? lookup(st.from) : { columns: [], rows: [[]] };
    var cols = table.columns;
    var colIndex = {};
    cols.forEach(function (c, i) { colIndex[c.name.toLowerCase()] = i; });
    var colNames = cols.map(function (c) { return c.name; });

    function rowCtx(row) {
      return {
        col: function (name) {
          var i = colIndex[name.toLowerCase()];
          if (i === undefined) {
            throw SqlError("UNRESOLVED_COLUMN", "A column with name `" + name + "` cannot be resolved." +
              (colNames.length ? " Did you mean one of: " + suggest(name, colNames) + "?" : " There is no FROM clause."));
          }
          return row[i];
        },
        agg: function () { throw SqlError("INVALID_AGGREGATE", "Aggregate functions are not allowed here. Filter groups with HAVING instead of WHERE."); },
      };
    }
    function groupCtx(rows) {
      var first = rows.length ? rowCtx(rows[0]) : null;
      return {
        col: function (name) { if (!first) { rowCtx([]).col(name); return null; } return first.col(name); },
        agg: function (n) { return aggregate(n, rows, rowCtx); },
      };
    }

    var src = table.rows;
    if (st.where) {
      if (hasAgg(st.where)) rowCtx([]).agg();
      src = src.filter(function (r) { return truthy(evaluate(st.where, rowCtx(r))); });
    }

    var items = [];
    st.items.forEach(function (it) {
      if (it.star) {
        if (!st.from) throw SqlError("INVALID_STAR", "SELECT * needs a FROM clause.");
        cols.forEach(function (c) { items.push({ expr: { k: "col", name: c.name }, name: c.name, type: c.type }); });
      } else {
        var isCol = it.expr.k === "col" && colIndex[it.expr.name.toLowerCase()] !== undefined;
        items.push({
          expr: it.expr,
          name: it.alias || (isCol ? cols[colIndex[it.expr.name.toLowerCase()]].name : it.text),
          type: isCol ? cols[colIndex[it.expr.name.toLowerCase()]].type : null,
        });
      }
    });

    var grouped = st.groupBy.length > 0 || items.some(function (it) { return hasAgg(it.expr); }) || hasAgg(st.having);
    if (st.having && !grouped) throw SqlError("HAVING_WITHOUT_GROUP", "HAVING needs GROUP BY or an aggregate in the SELECT list.");
    var out = [];
    if (grouped) {
      var groups = [], byKey = {};
      src.forEach(function (r) {
        var ctx = rowCtx(r);
        var key = JSON.stringify(st.groupBy.map(function (g) { return evaluate(g, ctx); }));
        if (!byKey[key]) { byKey[key] = []; groups.push(byKey[key]); }
        byKey[key].push(r);
      });
      if (!st.groupBy.length && !groups.length) groups.push([]);
      groups.forEach(function (g) {
        var ctx = groupCtx(g);
        if (st.having && !truthy(evaluate(st.having, ctx))) return;
        out.push({ vals: items.map(function (it) { return evaluate(it.expr, ctx); }), ctx: ctx });
      });
    } else {
      out = src.map(function (r) {
        var ctx = rowCtx(r);
        return { vals: items.map(function (it) { return evaluate(it.expr, ctx); }), ctx: ctx };
      });
    }

    if (st.distinct) {
      var seen = {};
      out = out.filter(function (o) { var k = JSON.stringify(o.vals); if (seen[k]) return false; seen[k] = true; return true; });
    }

    if (st.orderBy.length) {
      var aliasIdx = {};
      items.forEach(function (it, i) { if (!(it.name.toLowerCase() in aliasIdx)) aliasIdx[it.name.toLowerCase()] = i; });
      var keys = st.orderBy.map(function (o) {
        var e = o.expr, fn;
        if (e.k === "lit" && typeof e.v === "number") {
          var idx = e.v - 1;
          if (idx < 0 || idx >= items.length || Math.floor(e.v) !== e.v) throw SqlError("ORDER_BY_POS_OUT_OF_RANGE", "ORDER BY position " + e.v + " is not in the select list (1–" + items.length + ").");
          fn = function (o2) { return o2.vals[idx]; };
        } else if (e.k === "col" && e.name.toLowerCase() in aliasIdx) {
          var ai = aliasIdx[e.name.toLowerCase()];
          fn = function (o2) { return o2.vals[ai]; };
        } else {
          fn = function (o2) { return evaluate(e, o2.ctx); };
        }
        return { fn: fn, desc: o.desc, nullsFirst: o.nullsFirst == null ? !o.desc : o.nullsFirst };
      });
      var decorated = out.map(function (o, i) { return { o: o, i: i, k: keys.map(function (k) { return k.fn(o); }) }; });
      decorated.sort(function (a, b) {
        for (var j = 0; j < keys.length; j++) {
          var x = a.k[j], y = b.k[j];
          if (x == null && y == null) continue;
          if (x == null) return keys[j].nullsFirst ? -1 : 1;
          if (y == null) return keys[j].nullsFirst ? 1 : -1;
          var c = compare(x, y);
          if (c !== 0) return keys[j].desc ? -c : c;
        }
        return a.i - b.i;
      });
      out = decorated.map(function (d) { return d.o; });
    }

    var total = out.length;
    var end = st.limit != null ? st.offset + st.limit : undefined;
    out = out.slice(st.offset, end);
    var truncated = out.length > MAX_ROWS;
    if (truncated) out = out.slice(0, MAX_ROWS);
    var rows = out.map(function (o) { return o.vals; });

    return {
      kind: "table",
      columns: items.map(function (it) { return it.name; }),
      types: items.map(function (it, i) { return it.type || inferType(rows.map(function (r) { return r[i]; })); }),
      rows: rows,
      total: total,
      truncated: truncated,
    };
  }

  root.MiniSQL = { execute: execute, tokenize: tokenize, SqlError: SqlError, HELP: HELP };
})(typeof window !== "undefined" ? window : this);
