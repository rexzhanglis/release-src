import request from '@/utils/request'

// 在jira中操作的api

export function getReleaseIssueKey() {
  return request({
    url: '/jira/get_release_issue_key/',
    method: 'get'
  })
}

export function getReleaseIssueVersion(params) {
  return request({
    url: '/jira/get_release_issue_version/',
    method: 'get',
    params
  })
}

export function getMdlReleaseIssueKey() {
  return request({
    url: '/jira/get_mdl_release_issue_key/',
    method: 'get'
  })
}

export function getMdlReleaseIssueVersion(params) {
  return request({
    url: '/jira/get_mdl_release_issue_version/',
    method: 'get',
    params
  })
}
