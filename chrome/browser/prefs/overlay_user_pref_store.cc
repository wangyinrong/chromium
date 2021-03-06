// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "chrome/browser/prefs/overlay_user_pref_store.h"

#include "base/memory/scoped_ptr.h"
#include "base/values.h"

OverlayUserPrefStore::OverlayUserPrefStore(
    PersistentPrefStore* underlay)
    : underlay_(underlay) {
  underlay_->AddObserver(this);
}

OverlayUserPrefStore::~OverlayUserPrefStore() {
  underlay_->RemoveObserver(this);
}

bool OverlayUserPrefStore::IsSetInOverlay(const std::string& key) const {
  return overlay_.GetValue(key, NULL);
}

void OverlayUserPrefStore::AddObserver(PrefStore::Observer* observer) {
  observers_.AddObserver(observer);
}

void OverlayUserPrefStore::RemoveObserver(PrefStore::Observer* observer) {
  observers_.RemoveObserver(observer);
}

size_t OverlayUserPrefStore::NumberOfObservers() const {
  return observers_.size();
}

bool OverlayUserPrefStore::IsInitializationComplete() const {
  return underlay_->IsInitializationComplete();
}

PrefStore::ReadResult OverlayUserPrefStore::GetValue(
    const std::string& key,
    const Value** result) const {
  // If the |key| shall NOT be stored in the overlay store, there must not
  // be an entry.
  DCHECK(ShallBeStoredInOverlay(key) || !overlay_.GetValue(key, NULL));

  if (overlay_.GetValue(key, result))
    return READ_OK;
  return underlay_->GetValue(GetUnderlayKey(key), result);
}

PrefStore::ReadResult OverlayUserPrefStore::GetMutableValue(
    const std::string& key,
    Value** result) {
  if (!ShallBeStoredInOverlay(key))
    return underlay_->GetMutableValue(GetUnderlayKey(key), result);

  if (overlay_.GetValue(key, result))
    return READ_OK;

  // Try to create copy of underlay if the overlay does not contain a value.
  Value* underlay_value = NULL;
  PrefStore::ReadResult read_result =
      underlay_->GetMutableValue(GetUnderlayKey(key), &underlay_value);
  if (read_result != READ_OK)
    return read_result;

  *result = underlay_value->DeepCopy();
  overlay_.SetValue(key, *result);
  return READ_OK;
}

void OverlayUserPrefStore::SetValue(const std::string& key,
                                      Value* value) {
  if (!ShallBeStoredInOverlay(key)) {
    underlay_->SetValue(GetUnderlayKey(key), value);
    return;
  }

  if (overlay_.SetValue(key, value))
    ReportValueChanged(key);
}

void OverlayUserPrefStore::SetValueSilently(const std::string& key,
                                              Value* value) {
  if (!ShallBeStoredInOverlay(key)) {
    underlay_->SetValueSilently(GetUnderlayKey(key), value);
    return;
  }

  overlay_.SetValue(key, value);
}

void OverlayUserPrefStore::RemoveValue(const std::string& key) {
  if (!ShallBeStoredInOverlay(key)) {
    underlay_->RemoveValue(GetUnderlayKey(key));
    return;
  }

  if (overlay_.RemoveValue(key))
    ReportValueChanged(key);
}

bool OverlayUserPrefStore::ReadOnly() const {
  return false;
}

PersistentPrefStore::PrefReadError OverlayUserPrefStore::GetReadError() const {
  return PersistentPrefStore::PREF_READ_ERROR_NONE;
}

PersistentPrefStore::PrefReadError OverlayUserPrefStore::ReadPrefs() {
  // We do not read intentionally.
  OnInitializationCompleted(true);
  return PersistentPrefStore::PREF_READ_ERROR_NONE;
}

void OverlayUserPrefStore::ReadPrefsAsync(
    ReadErrorDelegate* error_delegate_raw) {
  scoped_ptr<ReadErrorDelegate> error_delegate(error_delegate_raw);
  // We do not read intentionally.
  OnInitializationCompleted(true);
}

void OverlayUserPrefStore::CommitPendingWrite() {
  underlay_->CommitPendingWrite();
  // We do not write our content intentionally.
}

void OverlayUserPrefStore::ReportValueChanged(const std::string& key) {
  FOR_EACH_OBSERVER(PrefStore::Observer, observers_, OnPrefValueChanged(key));
}

void OverlayUserPrefStore::RegisterOverlayPref(const std::string& key) {
  RegisterOverlayPref(key, key);
}

void OverlayUserPrefStore::RegisterOverlayPref(
    const std::string& overlay_key,
    const std::string& underlay_key) {
  DCHECK(!overlay_key.empty()) << "Overlay key is empty";
  DCHECK(overlay_to_underlay_names_map_.find(overlay_key) ==
         overlay_to_underlay_names_map_.end()) <<
      "Overlay key already registered";
  DCHECK(!underlay_key.empty()) << "Underlay key is empty";
  DCHECK(underlay_to_overlay_names_map_.find(underlay_key) ==
         underlay_to_overlay_names_map_.end()) <<
      "Underlay key already registered";
  overlay_to_underlay_names_map_[overlay_key] = underlay_key;
  underlay_to_overlay_names_map_[underlay_key] = overlay_key;
}

void OverlayUserPrefStore::OnPrefValueChanged(const std::string& key) {
  if (!overlay_.GetValue(GetOverlayKey(key), NULL))
    ReportValueChanged(GetOverlayKey(key));
}

void OverlayUserPrefStore::OnInitializationCompleted(bool succeeded) {
  FOR_EACH_OBSERVER(PrefStore::Observer, observers_,
                    OnInitializationCompleted(succeeded));
}

const std::string& OverlayUserPrefStore::GetOverlayKey(
    const std::string& underlay_key) const {
  NamesMap::const_iterator i =
      underlay_to_overlay_names_map_.find(underlay_key);
  return i != underlay_to_overlay_names_map_.end() ? i->second : underlay_key;
}

const std::string& OverlayUserPrefStore::GetUnderlayKey(
    const std::string& overlay_key) const {
  NamesMap::const_iterator i =
      overlay_to_underlay_names_map_.find(overlay_key);
  return i != overlay_to_underlay_names_map_.end() ? i->second : overlay_key;
}

bool OverlayUserPrefStore::ShallBeStoredInOverlay(
    const std::string& key) const {
  return overlay_to_underlay_names_map_.find(key) !=
      overlay_to_underlay_names_map_.end();
}
