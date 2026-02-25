const moment = require('moment')

export function formatTimeZone(time) {
  return moment(time).format('YYYY-MM-DD HH:mm:ss')
}

export function convertToSeconds(val) {
  const num = val.substring(0, val.length - 1)
  const unit = val.substring(val.length - 1, val.length)
  if (unit === 'm' || unit === 'M') {
    return num * 60
  } else if (unit === 'h' || unit === 'H') {
    return num * 60 * 60
  } else if (unit === 'd' || unit === 'D') {
    return num * 60 * 60 * 24
  }
}

