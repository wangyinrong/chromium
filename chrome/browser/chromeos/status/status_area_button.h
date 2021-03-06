// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef CHROME_BROWSER_CHROMEOS_STATUS_STATUS_AREA_BUTTON_H_
#define CHROME_BROWSER_CHROMEOS_STATUS_STATUS_AREA_BUTTON_H_
#pragma once

#include "base/compiler_specific.h"
#include "base/string16.h"
#include "ui/gfx/font.h"
#include "ui/views/controls/button/menu_button.h"
#include "ui/views/controls/button/menu_button_listener.h"

// Button to be used to represent status and allow menus to be popped up.
// Shows current button state by drawing a border around the current icon.
class StatusAreaButton : public views::MenuButton {
 public:
  // Different text styles for different types of backgrounds.
  enum TextStyle {
    WHITE_PLAIN_BOLD,
    GRAY_PLAIN_LIGHT,
    WHITE_HALOED_BOLD,
    GRAY_EMBOSSED_BOLD
  };

  class Delegate {
   public:
    // Commands to be passed to ExecuteCommand().
    enum Command {
      SHOW_LANGUAGE_OPTIONS,
      SHOW_NETWORK_OPTIONS,
      SHOW_ADVANCED_OPTIONS
    };

    // |command_id| can be any int, passed from the button to the delegate.
    virtual bool ShouldExecuteStatusAreaCommand(
        const views::View* button_view, int command_id) const = 0;

    virtual void ExecuteStatusAreaCommand(
        const views::View* button_view, int command_id) = 0;

    // Get the style that should currently be used in rendering the button's
    // text.
    virtual TextStyle GetStatusAreaTextStyle() const = 0;

    // Handle visibility changes (e.g. resize the status area).
    virtual void ButtonVisibilityChanged(views::View* button_view) = 0;

   protected:
    virtual ~Delegate() {}
  };

  StatusAreaButton(Delegate* button_delegate,
                   views::MenuButtonListener* menu_button_listener);
  virtual ~StatusAreaButton() {}
  virtual void PaintButton(gfx::Canvas* canvas, PaintButtonMode mode) OVERRIDE;

  // Overrides TextButton's SetText to clear max text size before seting new
  // text content so that the button size would fit the new text size.
  virtual void SetText(const string16& text) OVERRIDE;

  // views::MenuButton overrides.
  virtual bool Activate() OVERRIDE;

  // View overrides.
  virtual gfx::Size GetPreferredSize() OVERRIDE;
  virtual gfx::Insets GetInsets() const OVERRIDE;
  virtual void OnThemeChanged() OVERRIDE;
  virtual void SetVisible(bool visible) OVERRIDE;
  virtual bool HitTest(const gfx::Point& l) const OVERRIDE;

  // Sets menu_active_. Override this to perform additional actions when
  // menus are activated.
  virtual void SetMenuActive(bool active);

  // Refresh the style used to paint this button's text.  Schedules repaint.
  void UpdateTextStyle();

  bool menu_active() const { return menu_active_; }

 protected:
  Delegate* delegate() { return delegate_; }
  const Delegate* delegate() const { return delegate_; }

  // Subclasses should override these methods to return the correct dimensions.
  virtual int icon_height();
  virtual int icon_width();

  // Subclasses can override this method to return more or less padding.
  // The padding is added to both the left and right side.
  virtual int horizontal_padding();

  // Insets to use for this button.
  gfx::Insets insets_;

  // Controls whether or not the menu can be activated. This is independent of
  // IsEnabled state, so that we can prevent the menu from appearing without
  // affecting the appearance of the button.
  bool menu_active_;

 private:
  Delegate* delegate_;

  // Fonts used to render the button's text.
  gfx::Font light_font_;
  gfx::Font bold_font_;

  DISALLOW_COPY_AND_ASSIGN(StatusAreaButton);
};

#endif  // CHROME_BROWSER_CHROMEOS_STATUS_STATUS_AREA_BUTTON_H_
