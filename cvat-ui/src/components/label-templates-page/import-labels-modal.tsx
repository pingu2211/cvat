// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React, { useState } from 'react';
import Modal from 'antd/lib/modal';
import Upload, { RcFile } from 'antd/lib/upload';
import Text from 'antd/lib/typography/Text';
import Paragraph from 'antd/lib/typography/Paragraph';
import { InboxOutlined } from '@ant-design/icons';

import { SerializedLabel } from 'cvat-core-wrapper';

interface Props {
    open: boolean;
    onImport: (file: File) => Promise<SerializedLabel[]>;
    onImported: (fileName: string, labels: SerializedLabel[]) => void;
    onClose: () => void;
}

function ImportLabelsModal(props: Readonly<Props>): JSX.Element {
    const {
        open, onImport, onImported, onClose,
    } = props;
    const [file, setFile] = useState<RcFile | null>(null);
    const [importing, setImporting] = useState(false);

    const close = (): void => {
        setFile(null);
        onClose();
    };

    const handleImport = async (): Promise<void> => {
        if (!file) {
            return;
        }

        setImporting(true);
        try {
            const labels = await onImport(file);
            onImported(file.name, labels);
            setFile(null);
        } catch (_: unknown) {
            // the error is reported by the corresponding action
        } finally {
            setImporting(false);
        }
    };

    return (
        <Modal
            open={open}
            title='Import labels from a CVAT export'
            okText='Read labels'
            okButtonProps={{ disabled: !file }}
            confirmLoading={importing}
            onOk={handleImport}
            onCancel={close}
            destroyOnClose
            className='cvat-import-label-template-modal'
        >
            <Paragraph type='secondary'>
                Upload a file exported from another CVAT instance to start a template from its
                labels. A task or project backup, an annotations file, or an archive of either
                will do. Annotations in the file are ignored, only the labels are read.
            </Paragraph>
            <Upload.Dragger
                name='file'
                accept='.json,.xml,.zip'
                maxCount={1}
                fileList={file ? [file] : []}
                beforeUpload={(uploadedFile: RcFile) => {
                    setFile(uploadedFile);
                    return false;
                }}
                onRemove={() => {
                    setFile(null);
                    return true;
                }}
            >
                <p className='ant-upload-drag-icon'>
                    <InboxOutlined />
                </p>
                <Text className='ant-upload-text'>Click or drag a file here</Text>
            </Upload.Dragger>
        </Modal>
    );
}

export default React.memo(ImportLabelsModal);
