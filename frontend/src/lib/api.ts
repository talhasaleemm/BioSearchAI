export const API_URL = process.env.NODE_ENV === 'production'
  ? 'https://biosearchai-web-production.up.railway.app'
  : (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000');

interface FetchOptions extends RequestInit {
  requireAuth?: boolean;
}

export async function fetchApi(endpoint: string, options: FetchOptions = {}) {
  const { requireAuth = true, headers, ...restOptions } = options;
  
  const config: RequestInit = {
    ...restOptions,
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
  };

  if (requireAuth) {
    const token = typeof window !== 'undefined' ? sessionStorage.getItem('token') : null;
    if (token) {
      config.headers = {
        ...config.headers,
        Authorization: `Bearer ${token}`,
      };
    }
  }

  const response = await fetch(`${API_URL}${endpoint}`, config);

  if (!response.ok) {
    // Attempt to extract detail from FastAPI error response
    let errorMessage = 'An error occurred';
    try {
      const errorData = await response.json();
      if (typeof errorData.detail === 'string') {
        errorMessage = errorData.detail;
      } else if (Array.isArray(errorData.detail)) {
        errorMessage = errorData.detail.map((e: any) => e.msg).join(', ');
      }
    } catch {
      // Fallback if not JSON
      errorMessage = response.statusText;
    }
    throw new Error(errorMessage);
  }

  return response.json();
}
