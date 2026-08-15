# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from rest_framework.routers import DefaultRouter

from .views import LabelTemplateViewSet

router = DefaultRouter(trailing_slash=False)
router.register("label-templates", LabelTemplateViewSet)

urlpatterns = router.urls
