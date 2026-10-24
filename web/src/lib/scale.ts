export type Scale = (value: number) => number;

export function linearScale([d0, d1]: [number, number], [r0, r1]: [number, number]): Scale {
  const span = d1 - d0 || 1;
  return (value) => r0 + ((value - d0) / span) * (r1 - r0);
}

/** A "nice" step (1, 2, 2.5 or 5 x 10^n) that splits `max` into about `count` ticks. */
export function niceStep(max: number, count: number): number {
  if (max <= 0) return 1;
  const raw = max / count;
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const residual = raw / magnitude;
  const factor = residual <= 1 ? 1 : residual <= 2 ? 2 : residual <= 2.5 ? 2.5 : residual <= 5 ? 5 : 10;
  return factor * magnitude;
}

/** The top tick of niceTicks: `max` rounded up to a clean number. */
export function niceMax(max: number, count = 4): number {
  const ticks = niceTicks(max, count);
  return ticks[ticks.length - 1] || 1;
}

/** Ticks from 0 up to a rounded-up maximum that covers `max`. */
export function niceTicks(max: number, count = 4): number[] {
  const step = niceStep(max, count);
  const top = Math.ceil(max / step - 1e-9) * step;
  const ticks: number[] = [];
  for (let i = 0; i <= Math.round(top / step); i++) {
    ticks.push(Number((i * step).toPrecision(12)));
  }
  return ticks;
}
