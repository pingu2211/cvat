// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';
import Text from 'antd/lib/typography/Text';
import { Row, Col } from 'antd/lib/grid';
import Empty from 'antd/lib/empty';

import { LabelTemplatesQuery } from 'reducers';

interface Props {
    query: LabelTemplatesQuery;
}

function EmptyLabelTemplatesListComponent(props: Readonly<Props>): JSX.Element {
    const { query } = props;

    return (
        <div className='cvat-empty-label-templates-list'>
            <Empty description={!query.filter && !query.search ? (
                <Row justify='center' align='middle'>
                    <Col>
                        <Text strong>No label templates created yet ...</Text>
                    </Col>
                </Row>
            ) : (<Text>No results matched your search</Text>)}
            />
        </div>
    );
}

export default React.memo(EmptyLabelTemplatesListComponent);
