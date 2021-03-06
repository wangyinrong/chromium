// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef CONTENT_BROWSER_DOM_STORAGE_DOM_STORAGE_MESSAGE_FILTER_H_
#define CONTENT_BROWSER_DOM_STORAGE_DOM_STORAGE_MESSAGE_FILTER_H_
#pragma once

#include "base/memory/ref_counted.h"
#include "base/memory/scoped_ptr.h"
#include "content/public/browser/browser_message_filter.h"
#include "third_party/WebKit/Source/WebKit/chromium/public/WebStorageArea.h"
#include "webkit/dom_storage/dom_storage_context.h"
#include "webkit/dom_storage/dom_storage_types.h"

#ifdef ENABLE_NEW_DOM_STORAGE_BACKEND

class DOMStorageContextImpl;
class GURL;
class NullableString16;

namespace dom_storage {
class DomStorageArea;
class DomStorageContext;
class DomStorageHost;
}

// This class handles the logistics of DOM Storage within the browser process.
// It mostly ferries information between IPCs and the dom_storage classes.
class DOMStorageMessageFilter
    : public content::BrowserMessageFilter,
      public dom_storage::DomStorageContext::EventObserver {
 public:
  explicit DOMStorageMessageFilter(int unused, DOMStorageContextImpl* context);

 private:
  virtual ~DOMStorageMessageFilter();

  void InitializeInSequence();
  void UninitializeInSequence();

  // content::BrowserMessageFilter implementation
  virtual void OnFilterAdded(IPC::Channel* channel) OVERRIDE;
  virtual void OnFilterRemoved() OVERRIDE;
  virtual base::TaskRunner* OverrideTaskRunnerForMessage(
      const IPC::Message& message) OVERRIDE;
  virtual bool OnMessageReceived(const IPC::Message& message,
                                 bool* message_was_ok) OVERRIDE;

  // Message Handlers.
  void OnOpenStorageArea(int64 namespace_id, const string16& origin,
                         int64* storage_area_id);
  void OnCloseStorageArea(int64 storage_area_id);
  void OnLength(int64 storage_area_id, unsigned* length);
  void OnKey(int64 storage_area_id, unsigned index, NullableString16* key);
  void OnGetItem(int64 storage_area_id, const string16& key,
                 NullableString16* value);
  void OnSetItem(int64 storage_area_id, const string16& key,
                 const string16& value, const GURL& url,
                 WebKit::WebStorageArea::Result* result,
                 NullableString16* old_value);
  void OnRemoveItem(int64 storage_area_id, const string16& key,
                    const GURL& url, NullableString16* old_value);
  void OnClear(int64 storage_area_id, const GURL& url, bool* something_cleared);

  // DomStorageContext::EventObserver implementation which
  // sends events back to our renderer process.
  virtual void OnDomStorageItemSet(
      const dom_storage::DomStorageArea* area,
      const string16& key,
      const string16& new_value,
      const NullableString16& old_value,
      const GURL& page_url) OVERRIDE;
  virtual void OnDomStorageItemRemoved(
      const dom_storage::DomStorageArea* area,
      const string16& key,
      const string16& old_value,
      const GURL& page_url) OVERRIDE;
  virtual void OnDomStorageAreaCleared(
      const dom_storage::DomStorageArea* area,
      const GURL& page_url) OVERRIDE;

  void SendDomStorageEvent(
      const dom_storage::DomStorageArea* area,
      const GURL& page_url,
      const NullableString16& key,
      const NullableString16& new_value,
      const NullableString16& old_value);

  scoped_refptr<dom_storage::DomStorageContext> context_;
  scoped_ptr<dom_storage::DomStorageHost> host_;
  bool is_dispatching_message_;

  DISALLOW_IMPLICIT_CONSTRUCTORS(DOMStorageMessageFilter);
};

#endif  // ENABLE_NEW_DOM_STORAGE_BACKEND

#endif  // CONTENT_BROWSER_DOM_STORAGE_DOM_STORAGE_MESSAGE_FILTER_H_
