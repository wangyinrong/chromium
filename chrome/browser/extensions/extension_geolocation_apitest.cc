// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "chrome/browser/extensions/extension_apitest.h"
#include "content/test/mock_geolocation.h"

class GeolocationApiTest : public ExtensionApiTest {
 public:
  GeolocationApiTest() {
  }

  // InProcessBrowserTest
  virtual void SetUpInProcessBrowserTestFixture() {
    ExtensionApiTest::SetUpInProcessBrowserTestFixture();
    mock_geolocation_.Setup();
  }

  // InProcessBrowserTest
  virtual void TearDownInProcessBrowserTestFixture() {
    mock_geolocation_.TearDown();
  }

 private:
  content::MockGeolocation mock_geolocation_;
};

// http://crbug.com/68287
IN_PROC_BROWSER_TEST_F(GeolocationApiTest,
                       DISABLED_ExtensionGeolocationAccessFail) {
  // Test that geolocation cannot be accessed from extension without permission.
  ASSERT_TRUE(RunExtensionTest("geolocation/no_permission")) << message_;
}

IN_PROC_BROWSER_TEST_F(GeolocationApiTest, ExtensionGeolocationAccessPass) {
  // Test that geolocation can be accessed from extension with permission.
  ASSERT_TRUE(RunExtensionTest("geolocation/has_permission")) << message_;
}
