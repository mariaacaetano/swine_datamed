from django.test.runner import DiscoverRunner


class ProjectDiscoverRunner(DiscoverRunner):
    def build_suite(self, test_labels=None, **kwargs):
        return super().build_suite(test_labels or ["bulario", "regras", "semantica", "machine", "users", "suinos"], **kwargs)
