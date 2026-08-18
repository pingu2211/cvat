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
    activeInference: ActiveInference | null;
    cancelAutoAnnotation(): void;
    resumeAutoAnnotation(): void;
}

// a failed run is closed to get it out of the way rather than to stop it,
// so it is worth saying what is given up by doing so
function dismissConfirmation(activeInference: ActiveInference): { title: string, content: string } {
    if (activeInference.status !== RQStatus.FAILED) {
        return {
            title: 'You are going to cancel automatic annotation?',
            content: 'Reached progress will be lost. Continue?',
        };
    }

    return {
        title: 'You are going to dismiss automatic annotation?',
        content: activeInference.resumable ?
            'It will no longer be possible to resume it. Continue?' :
            'It will be removed from the task. Continue?',
    };
}

function AutomaticAnnotationProgress(props: Props): JSX.Element | null {
    const { activeInference, cancelAutoAnnotation, resumeAutoAnnotation } = props;
    if (!activeInference) {
        return null;
    }

    let textType: 'success' | 'danger' = 'success';
    if ([RQStatus.FAILED, RQStatus.UNKNOWN].includes(activeInference.status)) {
        textType = 'danger';
    }

    const failed = activeInference.status === RQStatus.FAILED;

    return (
        <Row justify='space-between' align='bottom'>
            <Col span={22} className='cvat-task-item-progress-wrapper'>
                <div>
                    <Text
                        type={activeInference.status === RQStatus.QUEUED ? undefined : textType}
                        strong
                    >
                        {((): JSX.Element => {
                            if (activeInference.status === RQStatus.QUEUED) {
                                return (
                                    <>
                                        Automatic annotation request queued
                                        <LoadingOutlined />
                                    </>
                                );
                            }

                            if (activeInference.status === RQStatus.STARTED) {
                                return (
                                    <>
                                        Automatic annotation is in progress
                                        <LoadingOutlined />
                                    </>
                                );
                            }

                            if (failed) {
                                return (<>Automatic annotation failed</>);
                            }

                            if (activeInference.status === RQStatus.UNKNOWN) {
                                return (<>Unknown status received</>);
                            }

                            return <>Automatic annotation accomplished</>;
                        })()}
                    </Text>
                    { failed && activeInference.resumable && (
                        <Button
                            className='cvat-resume-auto-annotation-button'
                            type='link'
                            size='small'
                            icon={<PlayCircleOutlined />}
                            onClick={() => {
                                Modal.confirm({
                                    title: 'You are going to resume automatic annotation?',
                                    content: 'It will continue from the frame the results were ' +
                                        'last saved at, and the existing annotations will be kept. Continue?',
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
                    percent={Math.floor(activeInference.progress)}
                    strokeColor={{
                        from: '#108ee9',
                        to: '#87d068',
                    }}
                    showInfo={false}
                    size='small'
                />
            </Col>
            <Col span={1} className='close-auto-annotation-icon'>
                <CVATTooltip title={failed ? 'Dismiss automatic annotation' : 'Cancel automatic annotation'}>
                    <CloseOutlined
                        onClick={() => {
                            Modal.confirm({
                                ...dismissConfirmation(activeInference),
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
