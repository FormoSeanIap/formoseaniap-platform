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

  return request;
}
