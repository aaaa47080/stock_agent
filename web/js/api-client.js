/**
 * Centralized API Client
 *
 * Single source of truth for all API communication.
 * Provides auth headers, error handling, timeout, and retry.
 *
 * Usage:
 *   const data = await AppAPI.get('/api/forum/boards');
 *   const result = await AppAPI.post('/api/forum/posts', { title: '...' });
 *   const result = await AppAPI.delete('/api/alerts/123');
 */
var DEFAULT_TIMEOUT = 15000;
var MAX_RETRIES = 3;
var RETRY_DELAY = 1000;

function getToken() {
    if (
        typeof AuthManager !== 'undefined' &&
        AuthManager.currentUser
    ) {
        return AuthManager.currentUser.accessToken || AuthManager.currentUser.token || null;
    }
    return null;
}

function buildHeaders(customHeaders) {
    var headers = {
        'Content-Type': 'application/json',
    };
    var token = getToken();
    if (token) {
        headers['Authorization'] = 'Bearer ' + token;
    }
    if (customHeaders) {
        Object.keys(customHeaders).forEach(function (key) {
            headers[key] = customHeaders[key];
        });
    }
    return headers;
}

function sleep(ms) {
    return new Promise(function (resolve) {
        setTimeout(resolve, ms);
    });
}

function parseErrorResponse(response) {
    return response.text().then(function (text) {
        try {
            var json = JSON.parse(text);
            if (typeof json.detail === 'string') {
                return json.detail;
            }
            if (Array.isArray(json.detail)) {
                return json.detail
                    .map(function (e) {
                        return (e.loc ? e.loc.join('.') + ': ' : '') + e.msg;
                    })
                    .join('\n');
            }
            if (json.message) {
                return json.message;
            }
            return JSON.stringify(json);
        } catch (e) {
            return 'Status ' + response.status + ': ' + response.statusText;
        }
    });
}

async function request(method, url, options) {
    options = options || {};
    var timeout = options.timeout || DEFAULT_TIMEOUT;
    var retries = options.retries !== undefined ? options.retries : MAX_RETRIES;
    var isIdempotent = method === 'GET' || method === 'HEAD' || method === 'OPTIONS';
    if (!isIdempotent) retries = 0;
    var body = options.body;
    var customHeaders = options.headers;
    var noContentType = options.noContentType || false;
    var lastError = null;

    var headers = buildHeaders(
        noContentType ? customHeaders : customHeaders
    );
    if (noContentType) {
        delete headers['Content-Type'];
    }

    for (var attempt = 0; attempt <= retries; attempt++) {
        try {
            var controller = new AbortController();
            var timer = setTimeout(function () {
                controller.abort();
            }, timeout);

            var fetchOptions = {
                method: method,
                headers: headers,
                signal: controller.signal,
                credentials: 'include',
            };
            if (body !== undefined && body !== null) {
                fetchOptions.body = typeof body === 'string' ? body : JSON.stringify(body);
            }

            var response = await fetch(url, fetchOptions);
            clearTimeout(timer);

            if (!response.ok) {
                var errorMsg = await parseErrorResponse(response);
                lastError = new Error(errorMsg);
                lastError.status = response.status;

                if (
                    response.status === 401 ||
                    response.status === 403 ||
                    response.status === 422
                ) {
                    throw lastError;
                }

                if (attempt < retries) {
                    await sleep(RETRY_DELAY * (attempt + 1));
                    continue;
                }
                throw lastError;
            }

            var contentType = response.headers.get('content-type') || '';
            if (contentType.includes('application/json')) {
                return await response.json();
            }
            return await response.text();
        } catch (err) {
            lastError = err;
            if (err.name === 'AbortError') {
                lastError = new Error('Request timeout (' + timeout + 'ms)');
                lastError.status = 0;
            }
            if (
                err.status === 401 ||
                err.status === 403 ||
                err.status === 422
            ) {
                throw err;
            }
            if (attempt < retries) {
                await sleep(RETRY_DELAY * (attempt + 1));
                continue;
            }
        }
    }
    throw lastError;
}

const AppAPI = {
    get: function (url, options) {
        return request('GET', url, options);
    },
    post: function (url, body, options) {
        options = options || {};
        options.body = body;
        return request('POST', url, options);
    },
    put: function (url, body, options) {
        options = options || {};
        options.body = body;
        return request('PUT', url, options);
    },
    patch: function (url, body, options) {
        options = options || {};
        options.body = body;
        return request('PATCH', url, options);
    },
    delete: function (url, options) {
        return request('DELETE', url, options);
    },
    getToken: getToken,
    buildHeaders: buildHeaders,
};

window.AppAPI = AppAPI;
export { AppAPI };
