from .evaluate_classification import Command as ClassificationCommand


class Command(ClassificationCommand):
    """Utiliza o mesmo protocolo da avaliação de classificação, sem duplicá-lo."""
    help = "Compara os oito motores reais com nomes compostos e contadores corretos."
    default_output = "config/machine/artifacts/comparative_metrics_v3.json"
