"""AetherFusion - Local Code Project Fusion Tool (v1.0.1).

Scans two local projects and generates a Markdown fusion report.
Supports module-level fusion planning from JSON project maps.
Supports dry-run patch preview generation (no files are modified).
Supports confirmed add_file application with rollback manifests.
Supports safe rollback with audit logging.
Supports whitelisted command verification for target projects.
Supports repair plan generation from verify results.
Supports import fix plan generation from repair plans.
Supports dependency plan generation from repair/import-fix plans.
Supports fusion-session orchestration for end-to-end pipeline runs.
"""

__version__ = "1.0.1"