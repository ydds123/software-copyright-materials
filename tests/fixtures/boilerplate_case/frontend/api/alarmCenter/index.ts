import request from '@/utils/request'

export function listAlarmCenter(query) {
  return request({ url: '/alertMg/alarmCenter/list', method: 'get', params: query })
}

export function getAlarmCenter(id) {
  return request({ url: '/alertMg/alarmCenter/' + id, method: 'get' })
}

export function addAlarmCenter(data) {
  return request({ url: '/alertMg/alarmCenter', method: 'post', data })
}

export function updateAlarmCenter(data) {
  return request({ url: '/alertMg/alarmCenter', method: 'put', data })
}

export function delAlarmCenter(ids) {
  return request({ url: '/alertMg/alarmCenter/' + ids, method: 'delete' })
}
