export type AnnotationBox = { box: number[]; label: string }
export type ResizeHandle = 'n' | 'ne' | 'e' | 'se' | 's' | 'sw' | 'w' | 'nw'

const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value))
export const cloneBoxes = (boxes: AnnotationBox[]) => boxes.map(box => ({ ...box, box: [...box.box] }))

export function drawBox(start: number[], end: number[]): number[] {
  const [x1, y1] = start.map(value => clamp(value, 0, 1))
  const [x2, y2] = end.map(value => clamp(value, 0, 1))
  return [Math.min(x1, x2), Math.min(y1, y2), Math.abs(x2 - x1), Math.abs(y2 - y1)]
}

export function moveBox(box: number[], dx: number, dy: number): number[] {
  return [clamp(box[0] + dx, 0, 1 - box[2]), clamp(box[1] + dy, 0, 1 - box[3]), box[2], box[3]]
}

/** Each edge moves independently; its opposite edge stays fixed, including at the image boundary. */
export function resizeBox(box: number[], handle: ResizeHandle, dx: number, dy: number, minimum = .003): number[] {
  let [left, top] = box
  let right = left + box[2], bottom = top + box[3]
  const minWidth = Math.min(minimum, box[2]), minHeight = Math.min(minimum, box[3])
  if (handle.includes('w')) left = clamp(left + dx, 0, right - minWidth)
  if (handle.includes('e')) right = clamp(right + dx, left + minWidth, 1)
  if (handle.includes('n')) top = clamp(top + dy, 0, bottom - minHeight)
  if (handle.includes('s')) bottom = clamp(bottom + dy, top + minHeight, 1)
  return [left, top, right - left, bottom - top]
}

export function replaceBox(boxes: AnnotationBox[], index: number, box: number[]): AnnotationBox[] {
  return boxes.map((item, i) => ({ ...item, box: [...(i === index ? box : item.box)] }))
}
