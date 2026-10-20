export type ErrorEnvelope = {
  error: { code: string; message_key: string; params: Record<string, unknown> };
};

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    public params: Record<string, unknown> = {},
  ) {
    super(code);
    this.name = 'ApiError';
  }
}

export async function toApiError(res: Response): Promise<ApiError> {
  try {
    const body = (await res.clone().json()) as Partial<ErrorEnvelope>;
    if (body?.error?.code) return new ApiError(res.status, body.error.code, body.error.params);
  } catch {
    /* non-JSON body (proxy error page, etc.) */
  }
  return new ApiError(res.status, res.status === 0 ? 'network' : 'unknown');
}
