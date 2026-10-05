---
title: Comparing two tables without ORDER BY
date: 2026-10-04
kind: note
tags: [spark, data-quality, migration]
summary: Row counts lie. A multiset of SHA-256 row hashes tells you exactly which rows differ, ignores row order, and still notices duplicates.
---

During a migration sign-off, "the counts match" is not evidence. Two tables can have the same number of rows and still disagree on every one of them. What you actually want to ask is whether the two tables hold **the same multiset of rows**.

The trick is to hash each row, then compare the hashes as a multiset: group by hash and count on each side. Row order stops mattering, and because you count instead of using `DISTINCT`, duplicates still show up.

```python
from pyspark.sql import DataFrame, functions as F

NULL = "\u0000NULL"  # concat_ws silently drops nulls, so give them a sentinel

def row_hashes(df: DataFrame, cols: list[str]) -> DataFrame:
    parts = [F.coalesce(F.col(c).cast("string"), F.lit(NULL)) for c in sorted(cols)]
    return df.select(F.sha2(F.concat_ws("\u0001", *parts), 256).alias("h"))

def multiset_diff(src: DataFrame, tgt: DataFrame, cols: list[str]) -> DataFrame:
    s = row_hashes(src, cols).groupBy("h").agg(F.count("*").alias("n_src"))
    t = row_hashes(tgt, cols).groupBy("h").agg(F.count("*").alias("n_tgt"))
    return (s.join(t, "h", "full_outer")
             .na.fill(0, ["n_src", "n_tgt"])
             .where(F.col("n_src") != F.col("n_tgt")))
```

An empty result means the tables match row for row. Anything else is your list of exact differences, and you can join the hashes back to the source to see the offending rows.

Things that bite in practice:

- **Normalize types before hashing.** `DECIMAL(18,2)` vs `DECIMAL(38,6)`, timestamps in different zones, and `CHAR` padding all hash differently while meaning the same thing. Cast both sides to one canonical form first.
- **Case and whitespace.** Teradata comparisons are often case-insensitive and Spark's are not. Decide which semantics you're validating and normalize on purpose.
- **Pick a separator that can't appear in the data.** That's why I use `\u0001`, so `("ab", "c")` and `("a", "bc")` don't collide.
- **Gate on a threshold, not on zero.** For huge tables, run the cheap checks first (schema diff, then counts) and only hash when they pass. Then apply a variance threshold that the validation team has agreed to in advance.
