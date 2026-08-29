import request from '@/utils/request'

export function listTicketAlarm(query) {
  return request({ url: '/alertMg/ticketAlarm/list', method: 'get', params: query })
}

export function getTicketAlarm(id) {
  return request({ url: '/alertMg/ticketAlarm/' + id, method: 'get' })
}

export function addTicketAlarm(data) {
  return request({ url: '/alertMg/ticketAlarm', method: 'post', data })
}

export function updateTicketAlarm(data) {
  return request({ url: '/alertMg/ticketAlarm', method: 'put', data })
}

export function delTicketAlarm(ids) {
  return request({ url: '/alertMg/ticketAlarm/' + ids, method: 'delete' })
}
