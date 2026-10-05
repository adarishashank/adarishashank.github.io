"""Layouts for the architecture diagrams. Coordinates are in SVG units; rows share y values so
edges between neighbours run straight. Every claim in a label comes from the resume."""

TOP, MID, BOT = 76, 156, 236


def n(id, x, y, label, sub="", kind="compute", icon=None, w=200, h=58, tip=None):
    return {"id": id, "x": x, "y": y, "w": w, "h": h, "label": label, "sub": sub, "kind": kind, "icon": icon,
            "tip": tip}


ARCH_PEPSICO = {
    "id": "arch-pepsico", "w": 1120, "h": 496,
    "title": "PepsiCo migration and Delta sync architecture",
    "desc": "Hive Metastore, Teradata and Synapse estates land in Unity Catalog; a config-driven Delta sync publishes "
            "curated data to ADLS for downstream consumers; every table passes a reconciliation sign-off gate.",
    "groups": [
        {"x": 16, "y": 34, "w": 228, "h": 290, "label": "LEGACY ESTATES", "kind": "source"},
        {"x": 280, "y": 34, "w": 252, "h": 290, "label": "UNITY CATALOG · GOVERNED", "kind": "govern"},
        {"x": 572, "y": 34, "w": 252, "h": 290, "label": "CONFIG-DRIVEN DELTA SYNC", "kind": "ingest"},
        {"x": 864, "y": 34, "w": 240, "h": 290, "label": "SERVE", "kind": "serve"},
        {"x": 16, "y": 350, "w": 1088, "h": 126, "label": "MIGRATION SIGN-OFF", "kind": "quality"},
    ],
    "nodes": [
        n("hms", 30, TOP, "Hive Metastore", "pan-European retail", "source", "db"),
        n("td", 30, MID, "Teradata", "APAC supply chain", "source", "db"),
        n("syn", 30, BOT, "Azure Synapse", "serverless SQL views", "source", "db"),
        n("mig", 296, TOP, "Migrated tables", "clone vs CTAS", "govern", "table", w=220),
        n("cur", 296, MID, "Curated Delta", "hash keys · QA checks", "gold", "layers", w=220),
        n("conv", 296, BOT, "Converted views", "Spark SQL · PySpark", "compute", "code", w=220),
        n("reg", 588, TOP, "JSON table registry", "tables · load modes", "ingest", "file", w=220),
        n("nb", 588, MID, "Sync notebook", "MERGE or full refresh", "compute", "cpu", w=220,
          tip="Parallel fan-out, run-overlap protection, dry-run mode and tiered verification"),
        n("adf", 588, BOT, "ADF orchestrator", "event-triggered runs", "ingest", "clock", w=220),
        n("m51", 880, 68, "51B rows", "one fact table, 1-hour window", "metric", w=208, h=72),
        n("adls", 880, MID, "ADLS Gen2", "curated Delta", "serve", "folder", w=208),
        n("cons", 880, BOT, "Downstream", "consumers & BI", "serve", "users", w=208),
        n("s1", 32, 392, "Schema diff", "columns · types", "quality", "table", w=196),
        n("s2", 246, 392, "Row counts", "per table", "quality", "search", w=196),
        n("s3", 460, 392, "SHA-256 multiset", "row-hash recon", "quality", "hash", w=196),
        n("s4", 674, 392, "Variance gate", "agreed thresholds", "quality", "filter", w=196),
        n("s5", 888, 392, "Production", "validation sign-off", "serve", "check", w=196),
    ],
    "edges": [
        {"from": "hms", "to": "mig", "flow": True},
        {"from": "td", "to": "conv"},
        {"from": "syn", "to": "conv", "flow": True},
        {"from": "mig", "to": "cur", "sides": "bt"},
        {"from": "conv", "to": "cur", "sides": "tb"},
        {"from": "cur", "to": "nb", "flow": True},
        {"from": "reg", "to": "nb", "sides": "bt", "dash": True},
        {"from": "adf", "to": "nb", "sides": "tb", "dash": True},
        {"from": "nb", "to": "adls", "flow": True},
        {"from": "adls", "to": "cons", "sides": "bt", "flow": True},
        {"from": "conv", "to": "s2", "sides": "bt", "label": "validate", "label_dy": -6},
        {"from": "s1", "to": "s2"}, {"from": "s2", "to": "s3"}, {"from": "s3", "to": "s4"},
        {"from": "s4", "to": "s5", "flow": True},
    ],
}

ARCH_TERADATA = {
    "id": "arch-teradata", "w": 1220, "h": 462,
    "title": "Teradata to Azure Databricks migration architecture",
    "desc": "Teradata, SAP BW and JDA / Blue Yonder sources flow through bronze, silver and gold Delta layers with an "
            "error quarantine, orchestrated by Databricks Workflows, with ADF and Event Grid gatekeepers publishing "
            "completion events.",
    "groups": [
        {"x": 16, "y": 34, "w": 228, "h": 290, "label": "SOURCES", "kind": "source"},
        {"x": 284, "y": 34, "w": 640, "h": 290, "label": "AZURE DATABRICKS · UNITY CATALOG · MEDALLION", "kind": "compute"},
        {"x": 964, "y": 34, "w": 240, "h": 290, "label": "GATEKEEPER", "kind": "ingest"},
        {"x": 16, "y": 348, "w": 1188, "h": 100, "label": "RELEASE AND GO-LIVE", "kind": "quality"},
    ],
    "nodes": [
        n("td", 30, TOP, "Teradata", "BTEQ · KSH · DDL", "source", "db"),
        n("sap", 30, MID, "SAP BW", "origin tables", "source", "db"),
        n("jda", 30, BOT, "JDA / Blue Yonder", "supply-chain feeds", "source", "cloud"),
        n("wf", 503, TOP, "Databricks Workflows", "Delta control tables", "ingest", "clock", w=232),
        n("bronze", 300, MID, "Bronze", "staging + validation", "bronze", "inbox"),
        n("silver", 514, MID, "Silver", "MERGE · hash keys", "silver", "repeat"),
        n("gold", 728, MID, "Gold", "Delta models", "gold", "layers", w=180),
        n("quar", 514, BOT, "Error quarantine", "rejected rows", "quality", "filter"),
        n("m4", 978, 68, "4 regions", "EU · APAC · AMESA · NA", "metric", w=212, h=72),
        n("adf", 978, MID, "ADF + Event Grid", "confirms every load", "ingest", "bolt", w=212,
          tip="Checks each load in a dependency set through the ADF REST API"),
        n("evt", 978, BOT, "Completion event", "publish downstream", "serve", "send", w=212),
        n("cicd", 32, 378, "Azure DevOps CI/CD", "PowerShell retry · backoff", "compute", "branch", w=270),
        n("parity", 326, 378, "Source-to-target parity", "case · overflow · concurrency", "quality", "check", w=300),
        n("rca", 650, 378, "Root-cause analysis", "documented for go-live", "govern", "book", w=260),
    ],
    "edges": [
        {"from": "td", "to": "bronze"},
        {"from": "sap", "to": "bronze", "flow": True},
        {"from": "jda", "to": "bronze"},
        {"from": "bronze", "to": "silver", "flow": True},
        {"from": "silver", "to": "gold", "flow": True},
        {"from": "silver", "to": "quar", "sides": "bt", "dash": True},
        {"from": "wf", "to": "silver", "sides": "bt", "dash": True},
        {"from": "gold", "to": "adf", "flow": True},
        {"from": "adf", "to": "evt", "sides": "bt", "flow": True},
    ],
}

ARCH_TWIN = {
    "id": "arch-twin", "w": 1228, "h": 470,
    "title": "Digital Twin real-time IoT architecture",
    "desc": "Plant sensors stream through IoT Hub, Event Hubs and Stream Analytics into Azure Data Explorer (Kusto) "
            "and SQL, feeding live dashboards and Logic Apps alerts, with ADF batch ETL alongside.",
    "groups": [
        {"x": 200, "y": 104, "w": 796, "h": 254, "label": "AZURE PAAS ESTATE · MONITORED WITH GRAFANA & DATADOG", "kind": "govern"},
    ],
    "nodes": [
        n("sensors", 16, 150, "Plant sensors", "telemetry", "source", "wave", w=170, h=60),
        n("iot", 214, 150, "IoT Hub", "device ingest", "ingest", "cloud", w=180, h=60),
        n("eh", 410, 150, "Event Hubs", "stream buffer", "ingest", "bolt", w=180, h=60),
        n("asa", 606, 150, "Stream Analytics", "windowed queries", "compute", "cpu", w=180, h=60),
        n("adx", 802, 150, "ADX (Kusto)", "real-time store", "serve", "db", w=180, h=60),
        n("dash", 1012, 150, "Live dashboards", "Angular · Power Apps", "serve", "chart", w=200, h=60),
        n("adf", 410, 274, "ADF batch ETL", "scheduled loads", "ingest", "clock", w=180, h=60),
        n("sql", 606, 274, "SQL Database", "curated history", "serve", "db", w=180, h=60),
        n("alerts", 802, 274, "Logic Apps", "automated alerts", "quality", "bell", w=180, h=60),
        n("m35", 200, 384, "−35%", "material wastage (program)", "metric", w=250, h=70),
        n("m20", 473, 384, "−20%", "Azure PaaS cost", "metric", w=250, h=70),
        n("m30", 746, 384, "+30%", "system performance", "metric", w=250, h=70),
    ],
    "edges": [
        {"from": "sensors", "to": "iot", "flow": True},
        {"from": "iot", "to": "eh", "flow": True},
        {"from": "eh", "to": "asa", "flow": True},
        {"from": "asa", "to": "adx", "flow": True},
        {"from": "adx", "to": "dash", "flow": True},
        {"from": "asa", "to": "sql", "sides": "bt"},
        {"from": "adf", "to": "sql"},
        {"from": "adx", "to": "alerts", "sides": "bt"},
    ],
}

OPS_LOOP = {
    "stages": [("Detect", "alert or request", "eye"), ("Triage", "impact & priority", "filter"),
               ("Resolve", "within SLA", "wrench"), ("Root cause", "ServiceNow record", "book"),
               ("Prevent", "no repeat incidents", "shield")],
    "value": "700", "label": "tickets resolved within SLA",
}

DIAGRAMS = [ARCH_PEPSICO, ARCH_TERADATA, ARCH_TWIN]
