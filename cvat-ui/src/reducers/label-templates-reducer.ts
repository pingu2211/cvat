// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import { AnyAction } from 'redux';
import { omit } from 'lodash';

import { AuthActionTypes } from 'actions/auth-actions';
import { LabelTemplatesActionsTypes } from 'actions/label-templates-actions';
import { LabelTemplatesState } from 'reducers';

const defaultState: LabelTemplatesState = {
    current: [],
    totalCount: 0,
    query: {
        page: 1,
        pageSize: 12,
        search: null,
        filter: null,
        sort: null,
    },
    activities: {
        deletes: {},
    },
    fetching: false,
};

export default function (
    state: LabelTemplatesState = defaultState,
    action: AnyAction,
): LabelTemplatesState {
    switch (action.type) {
        case LabelTemplatesActionsTypes.GET_LABEL_TEMPLATES: {
            return {
                ...state,
                fetching: true,
                query: {
                    ...state.query,
                    ...action.payload.query,
                },
            };
        }
        case LabelTemplatesActionsTypes.GET_LABEL_TEMPLATES_SUCCESS: {
            return {
                ...state,
                fetching: false,
                totalCount: action.payload.count,
                current: action.payload.templates,
            };
        }
        case LabelTemplatesActionsTypes.GET_LABEL_TEMPLATES_FAILED: {
            return {
                ...state,
                fetching: false,
            };
        }
        case LabelTemplatesActionsTypes.DELETE_LABEL_TEMPLATE: {
            const { templateId } = action.payload;
            return {
                ...state,
                activities: {
                    ...state.activities,
                    deletes: {
                        ...state.activities.deletes,
                        [templateId]: false,
                    },
                },
            };
        }
        case LabelTemplatesActionsTypes.DELETE_LABEL_TEMPLATE_SUCCESS: {
            const { templateId } = action.payload;
            return {
                ...state,
                activities: {
                    ...state.activities,
                    deletes: {
                        ...state.activities.deletes,
                        [templateId]: true,
                    },
                },
            };
        }
        case LabelTemplatesActionsTypes.DELETE_LABEL_TEMPLATE_FAILED: {
            const { templateId } = action.payload;
            return {
                ...state,
                activities: {
                    ...state.activities,
                    deletes: omit(state.activities.deletes, templateId),
                },
            };
        }
        case AuthActionTypes.LOGOUT_SUCCESS: {
            return { ...defaultState };
        }
        default:
            return state;
    }
}
