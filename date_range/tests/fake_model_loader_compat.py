# Copyright 2026 Grupo Nahuiik
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
"""FakeModelLoader compatible with Odoo 19 (replaces odoo_test_helper)."""
from __future__ import annotations

from unittest import mock

from odoo import models
from odoo.release import version_info


def _module_to_models():
    meta = models.MetaModel
    return getattr(meta, "module_to_models", meta._module_to_models__)


class _FakePackage:
    def __init__(self, name):
        self.name = name


class FakeModelLoader:
    def __init__(self, env, module):
        self.env = env
        self._module_name = module.split(".")[2]
        self._original_registry = {}
        self._original_module_to_models = {}

    def backup_registry(self):
        module_to_models = _module_to_models()
        self._original_registry = {}
        for model_name in list(self.env.registry):
            model = self.env.registry[model_name]
            self._original_registry[model_name] = {
                "base": model.__bases__,
                "_fields": dict(model._fields),
            }
        self._original_module_to_models = {
            key: list(value) for key, value in module_to_models.items()
        }

    def _clean_module_to_model(self):
        module_to_models = _module_to_models()
        for key, value in self._original_module_to_models.items():
            module_to_models[key] = list(value)
        for key in set(module_to_models.keys()) - set(
            self._original_module_to_models.keys()
        ):
            del module_to_models[key]

    def update_registry(self, odoo_models):
        module_to_models = _module_to_models()
        if hasattr(self.env, "flush_all"):
            self.env.flush_all()
        self._clean_module_to_model()
        for model in odoo_models:
            models_list = module_to_models.setdefault(self._module_name, [])
            if model not in models_list:
                models_list.append(model)
        with mock.patch.object(self.env.cr, "commit"):
            model_names = self.env.registry.load(
                self.env.cr, _FakePackage(self._module_name)
            )
            if version_info[0] >= 19:
                self.env.registry._setup_models__(self.env.cr, model_names)
            else:
                self.env.registry.setup_models(self.env.cr)
            self.env.registry.init_models(
                self.env.cr, model_names, {"module": self._module_name}
            )

    def restore_registry(self):
        registry = self.env.registry
        for model_name, ori in self._original_registry.items():
            model = registry[model_name]
            if hasattr(model, "_BaseModel__base_classes"):
                model._BaseModel__base_classes = ori["base"]
            model.__bases__ = ori["base"]
            model._fields = ori["_fields"]
        for model_name in list(registry):
            if model_name not in self._original_registry:
                del registry[model_name]
        self._clean_module_to_model()
        with mock.patch.object(self.env.cr, "commit"):
            if version_info[0] >= 19:
                registry._setup_models__(self.env.cr)
            else:
                registry.setup_models(self.env.cr)
