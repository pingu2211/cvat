// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React, { useEffect, useState } from 'react';
import Modal from 'antd/lib/modal';
import Input from 'antd/lib/input';
import Text from 'antd/lib/typography/Text';
import notification from 'antd/lib/notification';

import LabelsEditor from 'components/labels-editor/labels-editor';
import { SerializedLabel } from 'cvat-core-wrapper';
import { LabelTemplateData } from 'actions/label-templates-actions';

export interface LabelTemplateFormData {
    name: string;
    description: string;
    labels: SerializedLabel[];
}

interface Props {
    open: boolean;
    title: string;
    initialData: LabelTemplateFormData;
    onSubmit: (data: LabelTemplateData) => Promise<void>;
    onClose: () => void;
}

function LabelTemplateModal(props: Readonly<Props>): JSX.Element {
    const {
        open, title, initialData, onSubmit, onClose,
    } = props;

    const [name, setName] = useState(initialData.name);
    const [description, setDescription] = useState(initialData.description);
    const [labels, setLabels] = useState<SerializedLabel[]>(initialData.labels);
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        if (open) {
            setName(initialData.name);
            setDescription(initialData.description);
            setLabels(initialData.labels);
        }
    }, [open, initialData]);

    const handleSubmit = async (): Promise<void> => {
        if (!name.trim()) {
            notification.error({ message: 'The template must have a name' });
            return;
        }

        if (!labels.length) {
            notification.error({ message: 'The template must have at least one label' });
            return;
        }

        setSaving(true);
        try {
            await onSubmit({ name: name.trim(), description, labels });
            onClose();
        } catch (_: unknown) {
            // the error is reported by the corresponding action
        } finally {
            setSaving(false);
        }
    };

    return (
        <Modal
            open={open}
            title={title}
            width={800}
            okText='Save'
            confirmLoading={saving}
            onOk={handleSubmit}
            onCancel={onClose}
            destroyOnClose
            className='cvat-label-template-modal'
        >
            <Text className='cvat-text-color'>Name:</Text>
            <Input
                className='cvat-label-template-name-input'
                value={name}
                maxLength={256}
                placeholder='Traffic objects'
                onChange={(event) => setName(event.target.value)}
            />
            <Text className='cvat-text-color'>Description:</Text>
            <Input.TextArea
                className='cvat-label-template-description-input'
                value={description}
                maxLength={1024}
                autoSize={{ minRows: 1, maxRows: 3 }}
                placeholder='What this set of labels is for'
                onChange={(event) => setDescription(event.target.value)}
            />
            <Text className='cvat-text-color'>Labels:</Text>
            <LabelsEditor
                labels={labels}
                onSubmit={(updatedLabels) => {
                    setLabels(updatedLabels);
                }}
                enableFromModelCreator={false}
                enableFromTemplateCreator={false}
            />
        </Modal>
    );
}

export default React.memo(LabelTemplateModal);
