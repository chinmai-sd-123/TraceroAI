"use client";

import type { ComponentProps } from "react";

/** A select inside a GET form that submits the form when it changes. Without
 * JavaScript the form's own submit button does the same. */
export function AutoSubmitSelect(props: ComponentProps<"select">) {
  return <select {...props} onChange={(event) => event.currentTarget.form?.requestSubmit()} />;
}
