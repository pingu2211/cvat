# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from rest_framework import serializers

from cvat.apps.engine.models import AttributeType, LabelType
from cvat.apps.engine.serializers import BasicUserSerializer

from .models import LabelTemplate


class TemplateAttributeSerializer(serializers.Serializer):
    """
    An attribute specification, in the shape the project and task APIs accept.
    """

    name = serializers.CharField(max_length=64)
    mutable = serializers.BooleanField(default=False)
    input_type = serializers.ChoiceField(choices=AttributeType.choices())
    default_value = serializers.CharField(max_length=128, allow_blank=True, default="")
    values = serializers.ListField(
        child=serializers.CharField(allow_blank=True, max_length=200),
        allow_empty=True,
        default=list,
    )


class TemplateSublabelSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=64)
    color = serializers.CharField(max_length=8, allow_blank=True, default="")
    type = serializers.ChoiceField(choices=LabelType.choices(), default=str(LabelType.ANY))
    prompt = serializers.CharField(max_length=1024, allow_blank=True, default="")
    attributes = TemplateAttributeSerializer(many=True, allow_empty=True, default=list)


class TemplateLabelSerializer(TemplateSublabelSerializer):
    sublabels = TemplateSublabelSerializer(many=True, allow_empty=True, default=list)
    svg = serializers.CharField(allow_blank=True, default="")

    def validate(self, attrs):
        # DRF skips the defaults of nested fields on a PATCH, so the keys are
        # not guaranteed to be there. LabelTemplateWriteSerializer validates the
        # labels once more, on their own, to fill them in.
        sublabels = attrs.get("sublabels")
        if attrs.get("type") == str(LabelType.SKELETON):
            if not sublabels:
                raise serializers.ValidationError("A skeleton label must have sublabels")
        elif sublabels:
            raise serializers.ValidationError("Only a skeleton label can have sublabels")

        return attrs


class LabelTemplateReadSerializer(serializers.ModelSerializer):
    owner = BasicUserSerializer(read_only=True, required=False, allow_null=True)
    labels = TemplateLabelSerializer(many=True, read_only=True)

    class Meta:
        model = LabelTemplate
        fields = (
            "id",
            "name",
            "description",
            "labels",
            "owner",
            "organization",
            "created_date",
            "updated_date",
        )
        read_only_fields = fields
        extra_kwargs = {
            "organization": {"allow_null": True},
        }


class LabelTemplateWriteSerializer(serializers.ModelSerializer):
    labels = TemplateLabelSerializer(many=True, allow_empty=False)

    class Meta:
        model = LabelTemplate
        fields = (
            "id",
            "name",
            "description",
            "labels",
        )

    def validate_labels(self, value):
        if self.partial:
            # A partial update skips the defaults of the nested label fields,
            # which would store labels missing a type, a color and so on
            complete = TemplateLabelSerializer(data=self.initial_data["labels"], many=True)
            complete.is_valid(raise_exception=True)
            value = complete.validated_data

        names = [label["name"] for label in value]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise serializers.ValidationError(f"Label names must be unique, got: {duplicates}")

        return value

    def validate(self, attrs):
        request = self.context.get("request")
        name = attrs.get("name") or getattr(self.instance, "name", None)

        # Templates are named uniquely within an organization, or within the
        # templates of a user when they are created outside of one
        if request is not None and name is not None:
            organization = request.iam_context["organization"]
            queryset = LabelTemplate.objects.filter(name=name)
            if organization is not None:
                queryset = queryset.filter(organization=organization)
            else:
                queryset = queryset.filter(organization=None, owner=request.user)

            if self.instance is not None:
                queryset = queryset.exclude(pk=self.instance.pk)

            if queryset.exists():
                raise serializers.ValidationError(
                    {"name": "A label template with this name already exists"}
                )

        return attrs

    def to_representation(self, instance):
        return LabelTemplateReadSerializer(instance, context=self.context).data


class ExtractedLabelsSerializer(serializers.Serializer):
    """
    The labels found in an uploaded file, ready to be saved as a template.
    """

    labels = TemplateLabelSerializer(many=True, read_only=True)


class LabelExtractionRequestSerializer(serializers.Serializer):
    file = serializers.FileField(
        help_text="A file exported from CVAT: a task or project backup, "
        "a backup annotations.json, CVAT-for-images/video XML, "
        "a Datumaro or COCO annotation file, or a ZIP archive containing any of these."
    )
