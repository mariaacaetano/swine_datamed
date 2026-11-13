import hashlib
import json
from datetime import datetime, timezone

from django.conf import settings
from django.core.management.base import BaseCommand

from bulario.models import Doenca, Sintoma
from bulario.utils import clinical_symptoms, is_clinical_symptom


class Command(BaseCommand):
    help = 'Registra lacunas sintomáticas e marcadores de informação faltante, sem alterar a base.'

    def add_arguments(self, parser):
        parser.add_argument('--output', default='config/bulario/domain_audit_v3.json')

    def handle(self, *args, **options):
        root = settings.BASE_DIR.parent
        diseases = list(Doenca.objects.prefetch_related('sintomas'))
        symptoms = list(Sintoma.objects.all())
        missing = [d.nome for d in diseases if not clinical_symptoms(d)]
        report = {'criado_em': datetime.now(timezone.utc).isoformat(),
                  'doencas_cadastradas': len(diseases),
                  'doencas_com_perfil_sintomatico_documentado': len(diseases) - len(missing),
                  'sintomas_cadastrados': len(symptoms),
                  'sintomas_clinicos_documentados': sum(is_clinical_symptom(s.nome) for s in symptoms),
                  'marcadores_sem_informacao': sorted(s.nome for s in symptoms if not is_clinical_symptom(s.nome)),
                  'doencas_sem_sintomas_documentados': sorted(missing),
                  'sha256_fontes': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in sorted((root / 'base_data').glob('*.csv'))},
                  'interpretacao': 'Marcadores de informação faltante são preservados na origem, '
                                   'mas não fornecem sinais, evidências ou perfis diagnósticos. '
                                   'As lacunas não autorizam inventar associações; esta auditoria '
                                   'não valida a completude ou a correção clínica dos demais vínculos.'}
        output = root / options['output']
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'Auditoria da base gravada em {output}'))
