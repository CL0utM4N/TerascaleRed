//
//  kern_tr.hpp
//  TerascaleRed
//

#ifndef kern_tr_hpp
#define kern_tr_hpp

#include <Headers/kern_patcher.hpp>
#include <IOKit/pci/IOPCIDevice.h>

#include "kern_asic.hpp"

class TRDriver {
public:
	void init();

private:
	void processPatcher(KernelPatcher &patcher);
	bool consider(IOPCIDevice *pci);
	void findByConfigSpace();
	void logPCIInfo();
	void probeMMIO();

	IOPCIDevice *iGPU {nullptr};
	ChipFamily family {ChipFamily::Unknown};
	uint16_t deviceId {0};
	uint8_t revision {0};
};

#endif /* kern_tr_hpp */
