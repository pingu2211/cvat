# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from django.contrib.auth.models import User
from django.db import models

from cvat.apps.engine.models import TimestampedModel
from cvat.apps.organizations.models import Organization


class LabelTemplate(TimestampedModel):
    """
    A named, reusable set of label definitions.

    A template is not attached to a project or a task, it only stores the label
    specification that the label constructor copies into one. The specification
    is kept as JSON in the same shape the project and task APIs accept, so it
    can be handed over to them without a conversion step.
    """

    name = models.CharField(max_length=256)
    description = models.CharField(max_length=1024, blank=True, default="")
    labels = models.JSONField(default=list)

    owner = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    organization = models.ForeignKey(
        Organization, null=True, on_delete=models.CASCADE, related_name="+"
    )

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"],
                condition=models.Q(organization__isnull=False),
                name="label_template_unique_name_in_organization",
            ),
            models.UniqueConstraint(
                fields=["owner", "name"],
                condition=models.Q(organization__isnull=True),
                name="label_template_unique_name_for_owner",
            ),
        ]

    def __str__(self) -> str:
        return self.name
