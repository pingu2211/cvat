// Copyright (C) 2020-2022 Intel Corporation
// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';
import { Row, Col } from 'antd/lib/grid';
import { CloseOutlined, LoadingOutlined, PlayCircleOutlined } from '@ant-design/icons';
import Button from 'antd/lib/button';
import Text from 'antd/lib/typography/Text';
import Progress from 'antd/lib/progress';
import Modal from 'antd/lib/modal';

import CVATTooltip from 'components/common/cvat-tooltip';
import { RQStatus } from 'cvat-core-wrapper';
import { ActiveInference } from 'reducers';

interface Props {
    activeInferences: ActiveInference[];
    cancelAutoAnnotation(): void;
    resumeAutoAnnotation(): void;
}

// a failed run is closed to get it out of the way rather than to stop it,
// so it is worth saying what is given up by doing so
function dismissConfirmation(inferences: ActiveInference[]): { title: string, content: string } {
    const failed = inferences.filter((inference) => inference.status === RQStatus.FAILED);

    // as long as something is still running, closing stops it
    if (failed.length !== inferences.length) {
        return {
            title: 'You are going to cancel automatic annotation?',
            content: inferences.length === 1 ?
                'Reached progress will be lost. Continue?' :
                'All the requests of the task will be cancelled ' +
                'and reached progress will be lost. Continue?',
        };
    }

    const [it, they] = failed.length === 1 ? ['it', 'It'] : ['them', 'They'];
    return {
        title: 'You are going to dismiss automatic annotation?',
        content: failed.some((inference) => inference.resumable) ?
            `It will no longer be possible to resume ${it}. Continue?` :
            `${they} will be removed from the task. Continue?`,
    };
}

function describeSingle(inference: ActiveInference): JSX.Element {
    if (inference.status === RQStatus.QUEUED) {
        return (
            <>
                Automatic annotation request queued
                <LoadingOutlined />
            </>
        );
    }

    if (inference.status === RQStatus.STARTED) {
        return (
            <>
                Automatic annotation is in progress
                <LoadingOutlined />
            </>
        );
    }

    if (inference.status === RQStatus.FAILED) {
        return (<>Automatic annotation failed</>);
    }

    if (inference.status === RQStatus.UNKNOWN) {
        return (<>Unknown status received</>);
    }

    return <>Automatic annotation accomplished</>;
}

function describeSeveral(inferences: ActiveInference[]): JSX.Element {
    const count = (...statuses: RQStatus[]): number => (
        inferences.filter((inference) => statuses.includes(inference.status)).length
    );

    const running = count(RQStatus.STARTED);
    const queued = count(RQStatus.QUEUED);
    const failed = count(RQStatus.FAILED, RQStatus.UNKNOWN);

    const parts: string[] = [];
    if (running) {
        parts.push(`${running} running`);
    }
    if (queued) {
        parts.push(`${queued} queued`);
    }
    if (failed) {
        parts.push(`${failed} failed`);
    }
    if (!parts.length) {
        parts.push('in progress');
    }

    return (
        <>
            {`Automatic annotation of ${inferences.length} jobs: ${parts.join(', ')}`}
            { !!(running || queued) && <LoadingOutlined /> }
        </>
    );
}

function AutomaticAnnotationProgress(props: Props): JSX.Element | null {
    const { activeInferences, cancelAutoAnnotation, resumeAutoAnnotation } = props;
    if (!activeInferences.length) {
        return null;
    }

    const isFailed = activeInferences
        .some((inference) => [RQStatus.FAILED, RQStatus.UNKNOWN].includes(inference.status));
    const textType: 'success' | 'danger' = isFailed ? 'danger' : 'success';
    const isQueuedOnly = activeInferences.every((inference) => inference.status === RQStatus.QUEUED);
    const progress = activeInferences
        .reduce((sum, inference) => sum + inference.progress, 0) / activeInferences.length;

    const allFailed = activeInferences.every((inference) => inference.status === RQStatus.FAILED);
    // a run that stopped early can be picked up again where it left off
    const resumable = activeInferences
        .some((inference) => inference.status === RQStatus.FAILED && inference.resumable);

    return (
        <Row justify='space-between' align='bottom'>
            <Col span={22} className='cvat-task-item-progress-wrapper'>
                <div>
                    <Text
                        type={isQueuedOnly ? undefined : textType}
                        strong
                    >
                        {activeInferences.length === 1 ?
                            describeSingle(activeInferences[0]) :
                            describeSeveral(activeInferences)}
                    </Text>
                    { resumable && (
                        <Button
                            className='cvat-resume-auto-annotation-button'
                            type='link'
                            size='small'
                            icon={<PlayCircleOutlined />}
                            onClick={() => {
                                Modal.confirm({
                                    title: 'You are going to resume automatic annotation?',
                                    content: 'Every stopped request of the task will continue from the ' +
                                        'frame its results were last saved at, and the existing ' +
                                        'annotations will be kept. Continue?',
                                    okButtonProps: {
                                        type: 'primary',
                                    },
                                    onOk() {
                                        resumeAutoAnnotation();
                                    },
                                });
                            }}
                        >
                            Resume
                        </Button>
                    )}
                </div>
                <Progress
                    percent={Math.floor(progress)}
                    strokeColor={{
                        from: '#108ee9',
                        to: '#87d068',
                    }}
                    showInfo={false}
                    size='small'
                />
            </Col>
            <Col span={1} className='close-auto-annotation-icon'>
                <CVATTooltip title={allFailed ? 'Dismiss automatic annotation' : 'Cancel automatic annotation'}>
                    <CloseOutlined
                        onClick={() => {
                            Modal.confirm({
                                ...dismissConfirmation(activeInferences),
                                okButtonProps: {
                                    type: 'primary',
                                    danger: true,
                                },
                                onOk() {
                                    cancelAutoAnnotation();
                                },
                            });
                        }}
                    />
                </CVATTooltip>
            </Col>
        </Row>
    );
}

export default React.memo(AutomaticAnnotationProgress);
