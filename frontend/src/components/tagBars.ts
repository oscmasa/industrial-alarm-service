import type { TagCount } from '../api/types'

export function tagBars(items: TagCount[]) {
  const largestCount = Math.max(0, ...items.map((item) => item.event_count))
  return items.map((item) => ({
    ...item,
    width: largestCount > 0 ? Math.max(0, item.event_count) / largestCount * 100 : 0,
  }))
}
