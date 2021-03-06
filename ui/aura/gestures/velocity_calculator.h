// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef UI_AURA_GESTURES_VELOCITY_CALCULATOR_H_
#define UI_AURA_GESTURES_VELOCITY_CALCULATOR_H_
#pragma once

#include <vector>

#include "base/basictypes.h"
#include "base/memory/scoped_ptr.h"
#include "ui/aura/aura_export.h"

namespace aura {

class AURA_EXPORT VelocityCalculator {
 public:
  explicit VelocityCalculator(int bufferSize);
  ~VelocityCalculator();
  void PointSeen(int x, int y, int64 time);
  float XVelocity();
  float YVelocity();
  float VelocitySquared();
  void ClearHistory();

 private:
  struct Point {
    int x;
    int y;
    int64 time;
  };

  void UpdateVelocity();

  typedef scoped_array<Point> HistoryBuffer;
  HistoryBuffer buffer_;

  // index_ points directly after the last point added.
  int index_;
  size_t num_valid_entries_;
  const size_t buffer_size_;
  float x_velocity_;
  float y_velocity_;
  bool velocities_stale_;
  DISALLOW_COPY_AND_ASSIGN(VelocityCalculator);
};

}  // namespace aura

#endif  // UI_AURA_GESTURES_VELOCITY_CALCULATOR_H_
