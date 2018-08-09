import React, { Component } from 'react';
import PropTypes from 'prop-types';
import qs from 'qs';
import { connect } from 'react-redux';
import { getRunApi, getUUID } from '../Actions';
import RequestStateWrapper from './RequestStateWrapper';
import CompareRunView from './CompareRunView';

class CompareRunPage extends Component {
  static propTypes = {
    runUuids: PropTypes.arrayOf(String).isRequired,
  };

  componentWillMount() {
    this.requestIds = [];
    this.props.runUuids.forEach((runUuid) => {
      const requestId = getUUID();
      this.requestIds.push(requestId);
      this.props.dispatch(getRunApi(runUuid, requestId));
    });
  }

  render() {
    return (
      <RequestStateWrapper requestIds={this.requestIds}>
        <CompareRunView runUuids={this.props.runUuids}/>
      </RequestStateWrapper>
    );
  }
}

const mapStateToProps = (state, ownProps) => {
  const { location } = ownProps;
  const searchValues = qs.parse(location.search);
  const runUuids = JSON.parse(searchValues["?runs"]);
  return { runUuids };
};

export default connect(mapStateToProps)(CompareRunPage);
