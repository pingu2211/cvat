// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import './styles.scss';
import React, { useCallback, useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Row, Col } from 'antd/lib/grid';
import Spin from 'antd/lib/spin';
import Modal from 'antd/lib/modal';
import Pagination from 'antd/lib/pagination';
import { ExclamationCircleOutlined } from '@ant-design/icons';

import { CombinedState } from 'reducers';
import { shallowEqual } from 'utils/redux';
import { LabelTemplate, SerializedLabel } from 'cvat-core-wrapper';
import {
    createLabelTemplateAsync,
    deleteLabelTemplateAsync,
    extractLabelsAsync,
    getLabelTemplatesAsync,
    updateLabelTemplateAsync,
    LabelTemplateData,
} from 'actions/label-templates-actions';
import TopBar from './top-bar';
import LabelTemplateItem from './label-template-item';
import LabelTemplateModal, { LabelTemplateFormData } from './label-template-modal';
import ImportLabelsModal from './import-labels-modal';
import EmptyLabelTemplatesListComponent from './empty-list';

const EMPTY_FORM_DATA: LabelTemplateFormData = { name: '', description: '', labels: [] };

function templateNameFromFile(fileName: string): string {
    return fileName.replace(/\.[^.]+$/, '').slice(0, 256);
}

function LabelTemplatesPage(): JSX.Element {
    const dispatch = useDispatch();
    const {
        fetching, totalCount, query, templates, deletes, organization,
    } = useSelector((state: CombinedState) => ({
        fetching: state.labelTemplates.fetching,
        totalCount: state.labelTemplates.totalCount,
        query: state.labelTemplates.query,
        templates: state.labelTemplates.current,
        deletes: state.labelTemplates.activities.deletes,
        organization: state.organizations.current,
    }), shallowEqual);

    const [editing, setEditing] = useState<LabelTemplate | null>(null);
    const [formData, setFormData] = useState<LabelTemplateFormData | null>(null);
    const [importing, setImporting] = useState(false);

    useEffect(() => {
        dispatch(getLabelTemplatesAsync({ ...query, page: 1 }));
    }, [organization]);

    const onCreateTemplate = useCallback(() => {
        setEditing(null);
        setFormData(EMPTY_FORM_DATA);
    }, []);

    const onEditTemplate = useCallback((template: LabelTemplate) => {
        setEditing(template);
        setFormData({
            name: template.name,
            description: template.description,
            labels: template.labels,
        });
    }, []);

    const onImported = useCallback((fileName: string, labels: SerializedLabel[]) => {
        setImporting(false);
        setEditing(null);
        setFormData({ name: templateNameFromFile(fileName), description: '', labels });
    }, []);

    const onDeleteTemplate = useCallback((template: LabelTemplate) => {
        Modal.confirm({
            title: `Do you want to delete the "${template.name}" template?`,
            content: 'Projects and tasks created from it are not affected.',
            className: 'cvat-modal-confirm-delete-label-template',
            icon: <ExclamationCircleOutlined />,
            type: 'warning',
            okText: 'Delete',
            okButtonProps: { type: 'primary', danger: true },
            onOk: () => {
                dispatch(deleteLabelTemplateAsync(template))
                    .then(() => dispatch(getLabelTemplatesAsync(query)))
                    .catch(() => {});
            },
        });
    }, [query]);

    const onSubmit = useCallback(async (data: LabelTemplateData): Promise<void> => {
        if (editing) {
            await dispatch(updateLabelTemplateAsync(editing, data));
        } else {
            await dispatch(createLabelTemplateAsync(data));
        }

        await dispatch(getLabelTemplatesAsync(query));
    }, [editing, query]);

    const content = totalCount ? (
        <>
            <Row justify='center' align='middle'>
                <Col className='cvat-label-templates-list' md={22} lg={18} xl={16} xxl={14}>
                    {templates.map((template) => (
                        <LabelTemplateItem
                            key={template.id}
                            template={template}
                            deleting={(template.id as number) in deletes}
                            onEdit={onEditTemplate}
                            onDelete={onDeleteTemplate}
                        />
                    ))}
                </Col>
            </Row>
            <Row justify='center' align='middle' className='cvat-resource-pagination-wrapper'>
                <Col md={22} lg={18} xl={16} xxl={14}>
                    <Pagination
                        className='cvat-label-templates-pagination'
                        onChange={(page: number, pageSize: number) => {
                            dispatch(getLabelTemplatesAsync({ ...query, page, pageSize }));
                        }}
                        showSizeChanger
                        total={totalCount}
                        pageSize={query.pageSize}
                        current={query.page}
                        showQuickJumper
                    />
                </Col>
            </Row>
        </>
    ) : <EmptyLabelTemplatesListComponent query={query} />;

    return (
        <div className='cvat-label-templates-page'>
            <TopBar
                query={query}
                onApplySearch={(search: string | null) => {
                    dispatch(getLabelTemplatesAsync({ ...query, search: search || null, page: 1 }));
                }}
                onCreateTemplate={onCreateTemplate}
                onImportTemplate={() => setImporting(true)}
            />
            { fetching ? (
                <div className='cvat-empty-label-templates-list'>
                    <Spin size='large' className='cvat-spinner' />
                </div>
            ) : content }
            <LabelTemplateModal
                open={formData !== null}
                title={editing ? 'Edit the label template' : 'Create a label template'}
                initialData={formData ?? EMPTY_FORM_DATA}
                onSubmit={onSubmit}
                onClose={() => {
                    setFormData(null);
                    setEditing(null);
                }}
            />
            <ImportLabelsModal
                open={importing}
                onImport={(file: File) => dispatch(extractLabelsAsync(file))}
                onImported={onImported}
                onClose={() => setImporting(false)}
            />
        </div>
    );
}

export default React.memo(LabelTemplatesPage);
