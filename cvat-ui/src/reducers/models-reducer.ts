// Copyright (C) 2020-2022 Intel Corporation
// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import { omit } from 'lodash';
import { BoundariesActions, BoundariesActionTypes } from 'actions/boundaries-actions';
import { ModelsActionTypes, ModelsActions } from 'actions/models-actions';
import { AuthActionTypes, AuthActions } from 'actions/auth-actions';
import { SelectionActionsTypes, SelectionActions } from 'actions/selection-actions';
import { MLModel, ModelKind } from 'cvat-core-wrapper';
import { ActiveInference, ModelsState, SelectedResourceType } from '.';

type Inferences = ModelsState['inferences'];

// requests of a task are stored together, because a task may be annotated
// by one task-scoped request or by a request per job
function updateInference(inferences: Inferences, taskID: number, inference: ActiveInference): Inferences {
    const taskInferences = inferences[taskID] ?? [];
    const updated = taskInferences.some((existing) => existing.id === inference.id) ?
        taskInferences.map((existing) => (existing.id === inference.id ? inference : existing)) :
        [...taskInferences, inference];

    return { ...inferences, [taskID]: updated };
}

function removeInference(inferences: Inferences, taskID: number, inferenceID: string): Inferences {
    const taskInferences = (inferences[taskID] ?? []).filter((existing) => existing.id !== inferenceID);
    if (!taskInferences.length) {
        return omit(inferences, taskID);
    }

    return { ...inferences, [taskID]: taskInferences };
}

const defaultState: ModelsState = {
    initialized: false,
    fetching: false,
    creatingStatus: '',
    interactors: [],
    detectors: [],
    trackers: [],
    reid: [],
    modelRunnerIsVisible: false,
    modelRunnerTask: null,
    modelRunnerJobID: null,
    requestedInferenceIDs: {},
    inferences: {},
    totalCount: 0,
    query: {
        page: 1,
        pageSize: 12,
        id: null,
        search: null,
        filter: null,
        sort: null,
    },
    previews: {},
    selected: [],
};

export default function (
    state = defaultState,
    action: ModelsActions | AuthActions | BoundariesActions | SelectionActions,
): ModelsState {
    switch (action.type) {
        case ModelsActionTypes.GET_MODELS: {
            return {
                ...state,
                fetching: true,
                query: {
                    ...state.query,
                    ...action.payload.query,
                },
            };
        }
        case ModelsActionTypes.GET_MODELS_SUCCESS: {
            return {
                ...state,
                interactors: action.payload.models.filter((model: MLModel) => (
                    model.kind === ModelKind.INTERACTOR
                )),
                detectors: action.payload.models.filter((model: MLModel) => (
                    model.kind === ModelKind.DETECTOR
                )),
                trackers: action.payload.models.filter((model: MLModel) => (
                    model.kind === ModelKind.TRACKER
                )),
                reid: action.payload.models.filter((model: MLModel) => (
                    model.kind === ModelKind.REID
                )),
                totalCount: action.payload.count,
                initialized: true,
                fetching: false,
            };
        }
        case ModelsActionTypes.GET_MODELS_FAILED: {
            return {
                ...state,
                initialized: true,
                fetching: false,
            };
        }
        case ModelsActionTypes.SHOW_RUN_MODEL_DIALOG: {
            return {
                ...state,
                modelRunnerIsVisible: true,
                modelRunnerTask: action.payload.taskInstance,
                modelRunnerJobID: action.payload.jobID,
            };
        }
        case ModelsActionTypes.CLOSE_RUN_MODEL_DIALOG: {
            return {
                ...state,
                modelRunnerIsVisible: false,
                modelRunnerTask: null,
                modelRunnerJobID: null,
            };
        }
        case ModelsActionTypes.GET_INFERENCES_SUCCESS: {
            const { requestedInferenceIDs } = state;

            return {
                ...state,
                requestedInferenceIDs: {
                    ...requestedInferenceIDs,
                    ...action.payload.requestedInferenceIDs,
                },
            };
        }
        case ModelsActionTypes.GET_INFERENCE_STATUS_SUCCESS: {
            const { inferences, requestedInferenceIDs } = state;
            const { taskID, activeInference } = action.payload;

            if (activeInference.status === 'finished') {
                return {
                    ...state,
                    inferences: removeInference(inferences, taskID, activeInference.id),
                    requestedInferenceIDs: omit(requestedInferenceIDs, activeInference.id),
                };
            }

            return {
                ...state,
                inferences: updateInference(inferences, taskID, activeInference),
            };
        }
        case ModelsActionTypes.GET_INFERENCE_STATUS_FAILED: {
            const { inferences } = state;
            const { taskID, activeInference } = action.payload;

            return {
                ...state,
                inferences: updateInference(inferences, taskID, activeInference),
            };
        }
        case ModelsActionTypes.CANCEL_INFERENCE_SUCCESS: {
            const { inferences, requestedInferenceIDs } = state;
            const { taskID, activeInference } = action.payload;

            return {
                ...state,
                inferences: removeInference(inferences, taskID, activeInference.id),
                requestedInferenceIDs: omit(requestedInferenceIDs, activeInference.id),
            };
        }
        case ModelsActionTypes.GET_MODEL_PREVIEW: {
            const { modelID } = action.payload;
            const { previews } = state;
            return {
                ...state,
                previews: {
                    ...previews,
                    [modelID]: {
                        preview: '',
                        fetching: true,
                        initialized: false,
                    },
                },
            };
        }
        case ModelsActionTypes.GET_MODEL_PREVIEW_SUCCESS: {
            const { modelID, preview } = action.payload;
            const { previews } = state;
            return {
                ...state,
                previews: {
                    ...previews,
                    [modelID]: {
                        preview,
                        fetching: false,
                        initialized: true,
                    },
                },
            };
        }
        case ModelsActionTypes.GET_MODEL_PREVIEW_FAILED: {
            const { modelID } = action.payload;
            const { previews } = state;
            return {
                ...state,
                previews: {
                    ...previews,
                    [modelID]: {
                        ...previews[modelID],
                        fetching: false,
                        initialized: true,
                    },
                },
            };
        }
        case BoundariesActionTypes.RESET_AFTER_ERROR:
        case AuthActionTypes.LOGOUT_SUCCESS: {
            return { ...defaultState };
        }
        case SelectionActionsTypes.SELECT_RESOURCES: {
            if (action.payload.resourceType === SelectedResourceType.MODELS) {
                return {
                    ...state,
                    selected: Array.from(new Set([...state.selected, ...action.payload.resourceIds as number[]])),
                };
            }
            return state;
        }
        case SelectionActionsTypes.DESELECT_RESOURCES: {
            if (action.payload.resourceType === SelectedResourceType.MODELS) {
                return {
                    ...state,
                    selected: state.selected.filter((id) => !action.payload.resourceIds.includes(id)),
                };
            }
            return state;
        }
        case SelectionActionsTypes.CLEAR_SELECTED_RESOURCES: {
            return { ...state, selected: [] };
        }
        default: {
            return state;
        }
    }
}
