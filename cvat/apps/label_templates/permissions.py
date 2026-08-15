# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from enum import StrEnum

from django.conf import settings

from cvat.apps.iam.permissions import OpenPolicyAgentPermission

from .models import LabelTemplate


class LabelTemplatePermission(OpenPolicyAgentPermission):
    obj: LabelTemplate | None

    class Scopes(StrEnum):
        CREATE = "create"
        DELETE = "delete"
        UPDATE = "update"
        LIST = "list"
        VIEW = "view"

    @classmethod
    def create(cls, request, view, obj, iam_context):
        return [
            cls.create_base_perm(request, view, scope, iam_context, obj)
            for scope in cls.get_scopes(request, view, obj)
        ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.url = settings.IAM_OPA_DATA_URL + "/labeltemplates/allow"

    @classmethod
    def _get_scopes(cls, request, view, obj):
        Scopes = cls.Scopes
        return [
            {
                ("create", "POST"): Scopes.CREATE,
                ("destroy", "DELETE"): Scopes.DELETE,
                ("partial_update", "PATCH"): Scopes.UPDATE,
                ("update", "PUT"): Scopes.UPDATE,
                ("list", "GET"): Scopes.LIST,
                ("retrieve", "GET"): Scopes.VIEW,
                # Reading labels out of a file is only useful to fill in a new template
                ("extract_labels", "POST"): Scopes.CREATE,
            }[(view.action, request.method)]
        ]

    def get_resource(self):
        if self.obj:
            return {
                "id": self.obj.id,
                "owner": {"id": self.obj.owner_id},
                "organization": (
                    {"id": self.obj.organization_id}
                    if self.obj.organization_id is not None
                    else None
                ),
            }

        if self.scope == self.Scopes.CREATE:
            return {
                "id": None,
                "owner": {"id": self.user_id},
                "organization": ({"id": self.org_id} if self.org_id is not None else None),
            }

        return None
