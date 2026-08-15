// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';
import { Row, Col } from 'antd/lib/grid';
import Button from 'antd/lib/button';
import Input from 'antd/lib/input';
import Text from 'antd/lib/typography/Text';
import { PlusOutlined, UploadOutlined } from '@ant-design/icons';

import { LabelTemplatesQuery } from 'reducers';
import dimensions from 'utils/dimensions';

interface Props {
    query: LabelTemplatesQuery;
    onApplySearch(search: string | null): void;
    onCreateTemplate(): void;
    onImportTemplate(): void;
}

function TopBarComponent(props: Readonly<Props>): JSX.Element {
    const {
        query, onApplySearch, onCreateTemplate, onImportTemplate,
    } = props;

    return (
        <>
            <Row justify='center' align='middle'>
                <Col {...dimensions}>
                    <Text className='cvat-title'>Label templates</Text>
                    <br />
                    <Text type='secondary'>
                        Reusable sets of labels you can add to a project or a task
                        from the label constructor
                    </Text>
                </Col>
            </Row>
            <Row
                className='cvat-label-templates-page-top-bar cvat-resource-top-bar-wrapper'
                justify='center'
                align='middle'
            >
                <Col {...dimensions}>
                    <div className='cvat-label-templates-page-filters-wrapper'>
                        <Input.Search
                            enterButton
                            onSearch={(phrase: string) => onApplySearch(phrase)}
                            defaultValue={query.search ?? ''}
                            className='cvat-label-templates-page-search-bar'
                            placeholder='Search ...'
                        />
                        <div>
                            <Button
                                className='cvat-import-label-template-button'
                                icon={<UploadOutlined />}
                                onClick={onImportTemplate}
                            >
                                Import from CVAT export
                            </Button>
                            <Button
                                className='cvat-create-label-template-button'
                                type='primary'
                                icon={<PlusOutlined />}
                                onClick={onCreateTemplate}
                            >
                                Create a template
                            </Button>
                        </div>
                    </div>
                </Col>
            </Row>
        </>
    );
}

export default React.memo(TopBarComponent);
