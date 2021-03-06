// Copyright (c) 2011 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef CONTENT_PUBLIC_BROWSER_DEVTOOLS_HTTP_HANDLER_DELEGATE_H_
#define CONTENT_PUBLIC_BROWSER_DEVTOOLS_HTTP_HANDLER_DELEGATE_H_
#pragma once

#include <string>
#include <vector>

namespace net {
class URLRequestContext;
}

namespace content {

class WebContents;

class DevToolsHttpHandlerDelegate {
 public:
  typedef std::vector<WebContents*> InspectableTabs;
  virtual ~DevToolsHttpHandlerDelegate() {}

  // Should return discovery page HTML that should list available tabs
  // and provide attach links. Called on the IO thread.
  virtual std::string GetDiscoveryPageHTML() = 0;

  // Should return URL request context for issuing requests against devtools
  // webui or NULL if no context is available. Called on the IO thread.
  virtual net::URLRequestContext* GetURLRequestContext() = 0;

  // Returns true if and only if frontend resources are bundled.
  virtual bool BundlesFrontendResources() = 0;

  // Returns URL that front-end files are available at, empty string if
  // no internal server is available.
  virtual std::string GetFrontendResourcesBaseURL() = 0;
};

}  // namespace content

#endif  // CONTENT_PUBLIC_BROWSER_DEVTOOLS_HTTP_HANDLER_DELEGATE_H_
