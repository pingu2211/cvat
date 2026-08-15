// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React, { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import { Row, Col } from 'antd/lib/grid';
import Select from 'antd/lib/select';
import InputNumber from 'antd/lib/input-number';
import Text from 'antd/lib/typography/Text';

import { getCore, Project } from 'cvat-core-wrapper';
import CVATTooltip from 'components/common/cvat-tooltip';
import { CombinedState } from 'reducers';

const core = getCore();

const NO_MODEL = '';

interface InheritedConfig {
    functionID: string;
    threshold: number | null;
}

interface Props {
    functionID: string;
    threshold: number | null;
    projectID?: number | null;
    onChange: (functionID: string, threshold: number | null) => void;
}

// Resolves the configuration a task falls back to when it has none of its own.
// The task page does not load the project, so it is fetched here when it is not in the store.
function useInheritedConfig(projectID: number | null | undefined): InheritedConfig | null {
    const cachedProject = useSelector((state: CombinedState) => (
        projectID ? state.projects.current.find((project) => project.id === projectID) ?? null : null
    ));
    const [inherited, setInherited] = useState<InheritedConfig | null>(null);

    useEffect(() => {
        const toConfig = (project: Project): InheritedConfig => ({
            functionID: project.autoAnnotationFunction,
            threshold: project.autoAnnotationThreshold,
        });

        if (!projectID) {
            setInherited(null);
            return undefined;
        }

        if (cachedProject) {
            setInherited(toConfig(cachedProject));
            return undefined;
        }

        let outdated = false;
        core.projects.get({ id: projectID }).then((projects: Project[]) => {
            if (!outdated && projects.length) {
                setInherited(toConfig(projects[0]));
            }
        }).catch(() => {
            // a project the user cannot read simply shows no inherited configuration
        });

        return () => { outdated = true; };
    }, [projectID, cachedProject]);

    return inherited;
}

export default function AutoAnnotationModelEditor(props: Props): JSX.Element {
    const {
        functionID, threshold, projectID, onChange,
    } = props;
    const detectors = useSelector((state: CombinedState) => state.models.detectors);
    const inheritedFrom = useInheritedConfig(projectID);

    // The threshold is edited locally and only submitted when the field is left,
    // so that typing a value does not send a request per keystroke
    const [draftThreshold, setDraftThreshold] = useState<number | null>(threshold);
    useEffect(() => setDraftThreshold(threshold), [threshold]);

    const inheritedFunctionID = functionID ? '' : (inheritedFrom?.functionID ?? '');
    const inheritedThreshold = inheritedFrom?.threshold ?? null;

    // A previously configured function may no longer be deployed; keep it selectable
    // so that opening this page does not silently drop the configuration
    const options = [
        {
            value: NO_MODEL,
            label: inheritedFunctionID ? `Inherited: ${inheritedFunctionID}` : 'No model',
        },
        ...detectors.map((model) => ({ value: `${model.id}`, label: model.name })),
    ];
    if (functionID && !detectors.some((model) => `${model.id}` === functionID)) {
        options.push({ value: functionID, label: `${functionID} (not deployed)` });
    }

    const submitThreshold = (): void => {
        if (functionID && draftThreshold !== threshold) {
            onChange(functionID, draftThreshold);
        }
    };

    return (
        <Row className='cvat-auto-annotation-model' align='middle' gutter={8}>
            <Col span={24}>
                <CVATTooltip title='Images added to this resource later are annotated with this model automatically'>
                    <Text strong className='cvat-text-color'>
                        Auto annotation model
                    </Text>
                </CVATTooltip>
            </Col>
            <Col span={16}>
                <Select
                    className='cvat-auto-annotation-model-selector'
                    value={functionID}
                    options={options}
                    onChange={(value: string) => {
                        // the threshold is meaningless without a function; when a function is
                        // picked while inheriting one, the inherited threshold seeds the new value
                        const currentThreshold = inheritedFunctionID ? inheritedThreshold : threshold;
                        onChange(value, value ? currentThreshold : null);
                    }}
                />
            </Col>
            <Col span={8}>
                <CVATTooltip title='Detection confidence threshold'>
                    <InputNumber
                        className='cvat-auto-annotation-model-threshold'
                        placeholder='Threshold'
                        disabled={!functionID}
                        min={0}
                        max={1}
                        step={0.05}
                        value={functionID ? draftThreshold : null}
                        onChange={(value) => setDraftThreshold(
                            typeof value === 'number' ? value : null,
                        )}
                        onBlur={submitThreshold}
                        onPressEnter={submitThreshold}
                    />
                </CVATTooltip>
            </Col>
        </Row>
    );
}
