// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef WEBKIT_PLUGINS_PPAPI_EVENT_CONVERSION_H_
#define WEBKIT_PLUGINS_PPAPI_EVENT_CONVERSION_H_

#include <vector>

#include "base/memory/linked_ptr.h"
#include "ppapi/c/ppb_gamepad.h"
#include "ppapi/c/ppb_input_event.h"
#include "third_party/WebKit/Source/WebKit/chromium/public/WebInputEvent.h"

struct PP_InputEvent;

namespace ppapi {
struct InputEventData;
}

namespace WebKit {
class WebGamepads;
class WebInputEvent;
}

namespace webkit {
namespace ppapi {

// Converts the given WebKit event to one or possibly multiple PP_InputEvents.
// The generated events will be filled into the given vector. On failure, no
// events will ge generated and the vector will be empty.
void CreateInputEventData(const WebKit::WebInputEvent& event,
                          std::vector< ::ppapi::InputEventData >* pp_events);

// Creates a WebInputEvent from the given PP_InputEvent.  If it fails, returns
// NULL.  The caller owns the created object on success.
WebKit::WebInputEvent* CreateWebInputEvent(
    const ::ppapi::InputEventData& event);

// Creates an array of WebInputEvents to make the given event look like a user
// input event on all platforms. |plugin_x| and |plugin_y| should be the
// coordinates of a point within the plugin's area on the page.
std::vector<linked_ptr<WebKit::WebInputEvent> > CreateSimulatedWebInputEvents(
    const ::ppapi::InputEventData& event,
    int plugin_x,
    int plugin_y);

// Returns the PPAPI event class for the given WebKit event type. The given
// type should not be "Undefined" since there's no corresponding PPAPI class.
PP_InputEvent_Class ClassifyInputEvent(WebKit::WebInputEvent::Type type);

// Translate from WebGamepads to the Gamepad API format
// PP_GamepadsSampleData.
void ConvertWebKitGamepadData(WebKit::WebGamepads& webkit_data,
                              PP_GamepadsSampleData* output_data);

}  // namespace ppapi
}  // namespace webkit

#endif  // WEBKIT_PLUGINS_PPAPI_EVENT_CONVERSION_H_
