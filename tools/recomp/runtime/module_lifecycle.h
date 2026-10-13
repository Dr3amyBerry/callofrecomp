#ifndef CODRECOMP_MODULE_LIFECYCLE_H
#define CODRECOMP_MODULE_LIFECYCLE_H
#include <stdint.h>
unsigned module_references(uint32_t base);
int module_unload(uint32_t base);
#endif
