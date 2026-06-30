#include <Arduino.h>

#include "bms_app.h"

void setup()
{
    (void)BMS_App_Init();
}

void loop()
{
    BMS_App_Run();
}
