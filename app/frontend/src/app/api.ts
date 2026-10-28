export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

async function readError(response: Response): Promise<string> {
  const text = await response.text().catch(() => '');
  if (!text) return '请求失败（' + response.status + '）';
  try {
    const body = JSON.parse(text);
    if (typeof body?.detail === 'string') return body.detail;
    if (body?.detail) return JSON.stringify(body.detail);
    return text.slice(0, 600);
  } catch {
    return text.slice(0, 600);
  }
}

export async function api(path: string, options?: RequestInit): Promise<any> {
  const response = await fetch('/api' + path, options);
  if (!response.ok) throw new ApiError(response.status, await readError(response));
  if (response.status === 204) return null;
  return response.json();
}

export type UploadTicket = {duplicate?: boolean; uploaded_bytes?: number; id?: string; [key: string]: any};

export function uploadDemo(file: File, config: {modules: string[]; parameters: object; players: string[]}, onProgress: (fraction: number) => void): Promise<UploadTicket> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open('POST', '/api/upload');
    request.responseType = 'text';
    request.upload.onprogress = event => {
      if (event.lengthComputable && event.total > 0) onProgress(event.loaded / event.total);
    };
    request.onerror = () => reject(new ApiError(0, '上传连接中断，请重试。'));
    request.onabort = () => reject(new ApiError(0, '上传已取消。'));
    request.onload = () => {
      let body: any = null;
      try {
        body = request.responseText ? JSON.parse(request.responseText) : null;
      } catch {
        body = null;
      }
      if (request.status >= 200 && request.status < 300) {
        onProgress(1);
        resolve(body || {});
        return;
      }
      const detail = typeof body?.detail === 'string' ? body.detail : body?.detail ? JSON.stringify(body.detail) : (request.responseText || '上传失败（' + request.status + '）');
      reject(new ApiError(request.status, String(detail).slice(0, 600)));
    };
    const form = new FormData();
    form.append('file', file);
    form.append('config', JSON.stringify(config));
    request.send(form);
  });
}

export function abortable(promise: Promise<any>, signal: AbortSignal): Promise<any> {
  return new Promise((resolve, reject) => {
    const abort = () => reject(new DOMException('aborted', 'AbortError'));
    if (signal.aborted) return abort();
    signal.addEventListener('abort', abort, {once: true});
    promise.then(value => {
      signal.removeEventListener('abort', abort);
      resolve(value);
    }, error => {
      signal.removeEventListener('abort', abort);
      reject(error);
    });
  });
}
