# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import SAFE_METHODS
from rest_framework.response import Response

from cvat.apps.iam.filters import ORGANIZATION_OPEN_API_PARAMETERS

from .label_extraction import LabelExtractionError, extract_labels
from .models import LabelTemplate
from .permissions import LabelTemplatePermission
from .serializers import (
    ExtractedLabelsSerializer,
    LabelExtractionRequestSerializer,
    LabelTemplateReadSerializer,
    LabelTemplateWriteSerializer,
)


@extend_schema(tags=["label templates"])
@extend_schema_view(
    retrieve=extend_schema(
        summary="Get label template details",
        responses={"200": LabelTemplateReadSerializer},
    ),
    list=extend_schema(
        summary="List label templates",
        responses={"200": LabelTemplateReadSerializer(many=True)},
    ),
    create=extend_schema(
        summary="Create a label template",
        request=LabelTemplateWriteSerializer,
        parameters=ORGANIZATION_OPEN_API_PARAMETERS,
        responses={"201": LabelTemplateReadSerializer},
    ),
    update=extend_schema(
        summary="Replace a label template",
        request=LabelTemplateWriteSerializer,
        responses={"200": LabelTemplateReadSerializer},
    ),
    partial_update=extend_schema(
        summary="Update a label template",
        request=LabelTemplateWriteSerializer,
        responses={"200": LabelTemplateReadSerializer},
    ),
    destroy=extend_schema(
        summary="Delete a label template",
        responses={"204": OpenApiResponse(description="The label template has been deleted")},
    ),
)
class LabelTemplateViewSet(viewsets.ModelViewSet):
    queryset = LabelTemplate.objects.select_related("owner").all()
    ordering = "-id"
    http_method_names = ["get", "post", "delete", "patch", "put"]

    search_fields = ("name", "description", "owner")
    simple_filters = ("name", "owner")
    filter_fields = (*simple_filters, "id", "updated_date")
    ordering_fields = list(filter_fields)
    lookup_fields = {"owner": "owner__username"}
    iam_supports_organization_params = True
    iam_permission_class = LabelTemplatePermission

    def get_serializer_class(self):
        if self.action == "extract_labels":
            return LabelExtractionRequestSerializer

        if self.request.method in SAFE_METHODS:
            return LabelTemplateReadSerializer

        return LabelTemplateWriteSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        if self.action == "list":
            perm = LabelTemplatePermission.create_scope_list(self.request)
            queryset = perm.filter(queryset)

        return queryset

    def perform_create(self, serializer):
        serializer.save(
            owner=self.request.user,
            organization=self.request.iam_context["organization"],
        )

    @extend_schema(
        summary="Read the labels of a file exported from CVAT",
        description="Returns the label specification described by an uploaded file, "
        "without creating a template from it. Annotations in the file are ignored.",
        request={"multipart/form-data": LabelExtractionRequestSerializer},
        responses={"200": ExtractedLabelsSerializer},
    )
    @action(
        detail=False,
        methods=["POST"],
        url_path="extract-labels",
        parser_classes=[MultiPartParser, FormParser],
    )
    def extract_labels(self, request):
        request_serializer = LabelExtractionRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)

        try:
            labels = extract_labels(request_serializer.validated_data["file"])
        except LabelExtractionError as ex:
            raise ValidationError(str(ex)) from ex

        return Response(ExtractedLabelsSerializer({"labels": labels}).data)
