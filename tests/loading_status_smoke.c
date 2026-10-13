#include "loading_status.h"
#include <stdio.h>
int main(void){
    loading_status status; loading_status_init(&status);
    if(loading_status_get(&status)!=1)return 1;
    loading_status_feed(&status,"----- FS_Sta");
    loading_status_feed(&status,"rtup -----\n");
    if(loading_status_get(&status)!=2)return 2;
    loading_status_feed(&status,"Parsing menu file:ui/main.menu\n");
    if(loading_status_get(&status)!=4)return 3;
    loading_status_frame(&status);
    if(loading_status_get(&status)!=4)return 4;
    loading_status_feed(&status,"--- Common Initialization Complete ---\n");
    if(loading_status_get(&status)!=6)return 5;
    loading_status_frame(&status);if(loading_status_get(&status)!=0)return 6;
    loading_status_feed(&status,"------ Server Initialization ------\nLoading surfaces...\n");
    if(loading_status_get(&status)!=5)return 7;
    loading_status_feed(&status,"----- Client Initialization Complete -----\n");
    loading_status_frame(&status);if(loading_status_get(&status)!=5)return 8;
    loading_status_feed(&status,"CL_InitCGame: 11.82 seconds\n");
    loading_status_frame(&status);if(loading_status_get(&status)!=0)return 9;
    puts("Loading state: split output, menu, mission, presentation barrier OK");return 0;
}
