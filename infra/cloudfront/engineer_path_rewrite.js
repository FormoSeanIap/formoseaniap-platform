function handler(event) {
  var request = event.request;
  var uri = request.uri;

  if (uri === '/engineer' || uri === '/engineer/') {
    request.uri = '/index.html';
  } else if (uri.startsWith('/engineer/')) {
    request.uri = uri.substring('/engineer'.length);
  }

  if (request.uri.endsWith('/')) {
    request.uri += 'index.html';
  }

  // Add a marker header so the /engineer/* cache behavior's cache policy can
  // include it in the cache key, preventing key collisions with the default
  // behavior after the URI rewrite (e.g. /engineer/projects.html rewritten to
  // /projects.html would otherwise share a cache entry with the main site's
  // /projects.html served by the default behavior).
  request.headers['x-origin'] = { value: 'engineering' };

  return request;
}
