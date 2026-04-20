function handler(event) {
  var request = event.request;
  var uri = request.uri;

  // The engineering site objects live under the /engineer/ prefix in the S3
  // bucket (e.g. engineer/index.html, engineer/projects.html). Keeping the
  // /engineer/ prefix in the URI means the CloudFront cache key for
  // /engineer/<path> stays distinct from the default behavior's cache key
  // for /<path>, preventing cross-contamination between the main site and
  // engineering site through the shared AWS-managed cache policy.
  //
  // This function only needs to resolve directory-style requests to their
  // index.html object, matching what the default behavior's
  // default_root_object setting does for "/".
  if (uri === '/engineer') {
    request.uri = '/engineer/index.html';
  } else if (uri.endsWith('/')) {
    request.uri += 'index.html';
  }

  return request;
}
