// Copyright (c) 2011 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "chrome/browser/status_icons/status_tray.h"

#include <algorithm>

#include "base/stl_util.h"
#include "chrome/browser/status_icons/status_icon.h"

StatusTray::StatusTray() {
}

StatusTray::~StatusTray() {
  RemoveAllIcons();
}

void StatusTray::RemoveAllIcons() {
  STLDeleteElements(&status_icons_);
}

StatusIcon* StatusTray::CreateStatusIcon() {
  StatusIcon* icon = CreatePlatformStatusIcon();
  if (icon)
    status_icons_.push_back(icon);
  return icon;
}

void StatusTray::RemoveStatusIcon(StatusIcon* icon) {
  StatusIconList::iterator iter = std::find(
      status_icons_.begin(), status_icons_.end(), icon);
  if (iter != status_icons_.end()) {
    // Free the StatusIcon from the list.
    delete *iter;
    status_icons_.erase(iter);
  }
}
