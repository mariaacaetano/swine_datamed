import hashlib
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from bulario.data_pipeline import FILES, read_structured_csv
from bulario.medication_quality import audit_medication_rows


class Command(BaseCommand):
    help = "Lista fármacos aprovados e bloqueados por falta de campos obrigatórios."

    def add_arguments(self, parser):
        parser.add_argument("--output", default="config/bulario/medication_quality_audit.json")

    def handle(self, *args, **options):
        root = settings.BASE_DIR.parent
        filename, marker = FILES["farmacos"]
        source = root / "base_data" / filename
        report = audit_medication_rows(read_structured_csv(source, marker))
        report.update({"fonte": str(source.relative_to(root)),
                       "sha256_fonte": hashlib.sha256(source.read_bytes()).hexdigest()})
        output = Path(options["output"])
        if not output.is_absolute():
            output = root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(
            f"{report['total_farmacos_aprovados']} fármacos aprovados; "
            f"{report['total_farmacos_bloqueados']} bloqueados "
            f"({report['total_bloqueados']} linhas incompletas). Auditoria: {output}"))
