// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import { getCore, LabelTemplate, SerializedLabel } from 'cvat-core-wrapper';
import { LabelTemplatesQuery } from 'reducers';
import {
    ActionUnion, createAction, ThunkAction, ThunkDispatch,
} from 'utils/redux';
import { filterNull } from 'utils/filter-null';

const cvat = getCore();

export enum LabelTemplatesActionsTypes {
    GET_LABEL_TEMPLATES = 'GET_LABEL_TEMPLATES',
    GET_LABEL_TEMPLATES_SUCCESS = 'GET_LABEL_TEMPLATES_SUCCESS',
    GET_LABEL_TEMPLATES_FAILED = 'GET_LABEL_TEMPLATES_FAILED',
    CREATE_LABEL_TEMPLATE = 'CREATE_LABEL_TEMPLATE',
    CREATE_LABEL_TEMPLATE_SUCCESS = 'CREATE_LABEL_TEMPLATE_SUCCESS',
    CREATE_LABEL_TEMPLATE_FAILED = 'CREATE_LABEL_TEMPLATE_FAILED',
    UPDATE_LABEL_TEMPLATE = 'UPDATE_LABEL_TEMPLATE',
    UPDATE_LABEL_TEMPLATE_SUCCESS = 'UPDATE_LABEL_TEMPLATE_SUCCESS',
    UPDATE_LABEL_TEMPLATE_FAILED = 'UPDATE_LABEL_TEMPLATE_FAILED',
    DELETE_LABEL_TEMPLATE = 'DELETE_LABEL_TEMPLATE',
    DELETE_LABEL_TEMPLATE_SUCCESS = 'DELETE_LABEL_TEMPLATE_SUCCESS',
    DELETE_LABEL_TEMPLATE_FAILED = 'DELETE_LABEL_TEMPLATE_FAILED',
    EXTRACT_LABELS_FAILED = 'EXTRACT_LABELS_FAILED',
}

const labelTemplatesActions = {
    getLabelTemplates: (query: Partial<LabelTemplatesQuery>) => createAction(
        LabelTemplatesActionsTypes.GET_LABEL_TEMPLATES, { query },
    ),
    getLabelTemplatesSuccess: (templates: LabelTemplate[], count: number) => createAction(
        LabelTemplatesActionsTypes.GET_LABEL_TEMPLATES_SUCCESS, { templates, count },
    ),
    getLabelTemplatesFailed: (error: any) => createAction(
        LabelTemplatesActionsTypes.GET_LABEL_TEMPLATES_FAILED, { error },
    ),
    createLabelTemplate: () => createAction(LabelTemplatesActionsTypes.CREATE_LABEL_TEMPLATE),
    createLabelTemplateSuccess: (template: LabelTemplate) => createAction(
        LabelTemplatesActionsTypes.CREATE_LABEL_TEMPLATE_SUCCESS, { template },
    ),
    createLabelTemplateFailed: (error: any) => createAction(
        LabelTemplatesActionsTypes.CREATE_LABEL_TEMPLATE_FAILED, { error },
    ),
    updateLabelTemplate: () => createAction(LabelTemplatesActionsTypes.UPDATE_LABEL_TEMPLATE),
    updateLabelTemplateSuccess: (template: LabelTemplate) => createAction(
        LabelTemplatesActionsTypes.UPDATE_LABEL_TEMPLATE_SUCCESS, { template },
    ),
    updateLabelTemplateFailed: (error: any) => createAction(
        LabelTemplatesActionsTypes.UPDATE_LABEL_TEMPLATE_FAILED, { error },
    ),
    deleteLabelTemplate: (templateId: number) => createAction(
        LabelTemplatesActionsTypes.DELETE_LABEL_TEMPLATE, { templateId },
    ),
    deleteLabelTemplateSuccess: (templateId: number) => createAction(
        LabelTemplatesActionsTypes.DELETE_LABEL_TEMPLATE_SUCCESS, { templateId },
    ),
    deleteLabelTemplateFailed: (templateId: number, error: any) => createAction(
        LabelTemplatesActionsTypes.DELETE_LABEL_TEMPLATE_FAILED, { templateId, error },
    ),
    extractLabelsFailed: (error: any) => createAction(
        LabelTemplatesActionsTypes.EXTRACT_LABELS_FAILED, { error },
    ),
};

export const getLabelTemplatesAsync = (query: Partial<LabelTemplatesQuery>): ThunkAction => (
    async (dispatch: ThunkDispatch): Promise<void> => {
        dispatch(labelTemplatesActions.getLabelTemplates(query));

        let result = null;
        try {
            result = await cvat.labelTemplates.get(filterNull(query));
        } catch (error) {
            dispatch(labelTemplatesActions.getLabelTemplatesFailed(error));
            return;
        }

        dispatch(labelTemplatesActions.getLabelTemplatesSuccess(Array.from(result), result.count));
    }
);

export interface LabelTemplateData {
    name: string;
    description: string;
    labels: SerializedLabel[];
}

export function createLabelTemplateAsync(data: LabelTemplateData): ThunkAction {
    return async function (dispatch) {
        const template = new cvat.classes.LabelTemplate(data);
        dispatch(labelTemplatesActions.createLabelTemplate());

        try {
            const createdTemplate = await template.save();
            dispatch(labelTemplatesActions.createLabelTemplateSuccess(createdTemplate));
        } catch (error) {
            dispatch(labelTemplatesActions.createLabelTemplateFailed(error));
            throw error;
        }
    };
}

export function updateLabelTemplateAsync(
    template: LabelTemplate, data: LabelTemplateData,
): ThunkAction {
    return async function (dispatch) {
        dispatch(labelTemplatesActions.updateLabelTemplate());

        try {
            // eslint-disable-next-line no-param-reassign
            template.name = data.name;
            // eslint-disable-next-line no-param-reassign
            template.description = data.description;
            // eslint-disable-next-line no-param-reassign
            template.labels = data.labels;
            const updatedTemplate = await template.save();
            dispatch(labelTemplatesActions.updateLabelTemplateSuccess(updatedTemplate));
        } catch (error) {
            dispatch(labelTemplatesActions.updateLabelTemplateFailed(error));
            throw error;
        }
    };
}

export function deleteLabelTemplateAsync(template: LabelTemplate): ThunkAction {
    return async function (dispatch) {
        dispatch(labelTemplatesActions.deleteLabelTemplate(template.id as number));

        try {
            await template.delete();
            dispatch(labelTemplatesActions.deleteLabelTemplateSuccess(template.id as number));
        } catch (error) {
            dispatch(labelTemplatesActions.deleteLabelTemplateFailed(template.id as number, error));
            throw error;
        }
    };
}

export function extractLabelsAsync(file: File): ThunkAction<Promise<SerializedLabel[]>> {
    return async function (dispatch) {
        try {
            return await cvat.labelTemplates.extractLabels(file);
        } catch (error) {
            dispatch(labelTemplatesActions.extractLabelsFailed(error));
            throw error;
        }
    };
}

export type LabelTemplatesActions = ActionUnion<typeof labelTemplatesActions>;
