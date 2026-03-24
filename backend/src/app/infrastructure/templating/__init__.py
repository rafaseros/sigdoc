from functools import lru_cache

from app.domain.ports.template_engine import TemplateEngine
from app.infrastructure.templating.docxtpl_engine import DocxTemplateEngine


@lru_cache
def get_template_engine() -> TemplateEngine:
    return DocxTemplateEngine()
