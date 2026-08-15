# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from django.apps import AppConfig


class LabelTemplatesConfig(AppConfig):
    name = "cvat.apps.label_templates"

    def ready(self):
        from cvat.apps.iam.permissions import load_app_iam_rules

        load_app_iam_rules(self)
