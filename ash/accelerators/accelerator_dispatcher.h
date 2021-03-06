// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef ASH_ACCELERATORS_ACCELERATOR_DISPATCHER_H_
#define ASH_ACCELERATORS_ACCELERATOR_DISPATCHER_H_
#pragma once

#include "ash/ash_export.h"
#include "base/message_loop.h"
#include "ui/aura/window.h"
#include "ui/aura/window_observer.h"

namespace ash {

// Dispatcher for handling accelerators in ash.
// Wraps a nested dispatcher to which control is passed if no accelerator key
// has been pressed.
// TODO(pkotwicz): Port AcceleratorDispatcher to mac.
// TODO(pkotwicz): Add support for a |nested_dispatcher| which sends
//  events to a system IME.
class ASH_EXPORT AcceleratorDispatcher : public MessageLoop::Dispatcher,
                                         public aura::WindowObserver {
 public:
  explicit AcceleratorDispatcher(MessageLoop::Dispatcher* nested_dispatcher,
                                 aura::Window* associated_window);
  virtual ~AcceleratorDispatcher();

#if defined(USE_X11)
  virtual base::MessagePumpDispatcher::DispatchStatus Dispatch(
      XEvent* xev) OVERRIDE;
#elif defined(OS_WIN)
  bool AcceleratorDispatcher::Dispatch(const MSG& msg) OVERRIDE;
#endif

  // aura::WindowObserver overrides:
  virtual void OnWindowDestroying(aura::Window* window) OVERRIDE;

 private:
  MessageLoop::Dispatcher* nested_dispatcher_;

  // Window associated with |nested_dispatcher_| which is used to determine
  // whether the |nested_dispatcher_| is allowed to receive events.
  aura::Window* associated_window_;

  DISALLOW_COPY_AND_ASSIGN(AcceleratorDispatcher);
};

}  // namespace ash

#endif  // ASH_ACCELERATORS_ACCELERATOR_DISPATCHER_H_
