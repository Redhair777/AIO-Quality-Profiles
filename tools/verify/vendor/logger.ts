/**
 * LOGGING STUB — NOT vendored from AIOStreams.
 *
 * The real AIOStreams `logging/logger.ts` is a pino-based logger with many
 * transitive dependencies (pino, pino-pretty, redact helpers, a ring buffer,
 * config integration). None of that affects stream-expression evaluation
 * semantics — the vendored evaluator only uses `createLogger(...)` to emit
 * debug/error messages. This no-op stub keeps the vendored evaluator
 * self-contained and reproducible on a fresh clone.
 *
 * If byte-for-byte fidelity of logging behavior is ever required, vendor the
 * real `logging/logger.ts` and its closure instead.
 */

export interface Logger {
  silly: (...args: unknown[]) => void;
  debug: (...args: unknown[]) => void;
  info: (...args: unknown[]) => void;
  warn: (...args: unknown[]) => void;
  error: (...args: unknown[]) => void;
}

const noop = (..._args: unknown[]): void => {};

const defaultLogger: Logger = {
  silly: noop,
  debug: noop,
  info: noop,
  warn: noop,
  error: noop,
};

export function createLogger(_name?: string): Logger {
  return defaultLogger;
}