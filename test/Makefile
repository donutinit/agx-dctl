# Arma la referencia (darktable) y el DCTL compilado como C, y corre las pruebas.
CC = cc
CFLAGS = -O2 -fno-fast-math
BUILD = build
LCMS = upstream/lcms2
LCMS_SRC = $(wildcard $(LCMS)/src/*.c)
LCMS_OBJ = $(patsubst $(LCMS)/src/%.c,$(BUILD)/lcms2/%.o,$(LCMS_SRC))

all: $(BUILD)/dtref $(BUILD)/dctl_run $(BUILD)/dctl_run_gpusim

upstream/darktable/agx.c:
	./fetch.sh

$(BUILD)/lcms2/%.o: $(LCMS)/src/%.c
	@mkdir -p $(dir $@)
	$(CC) -O2 -I$(LCMS)/include -c $< -o $@

$(BUILD)/liblcms2.a: $(LCMS_OBJ)
	ar rcs $@ $^

$(BUILD)/dtref_extract.inc: extract.py upstream/darktable/agx.c
	python3 extract.py upstream/darktable $@

$(BUILD)/dtref: dtref.c dt_shim.h $(BUILD)/dtref_extract.inc $(BUILD)/liblcms2.a
	$(CC) $(CFLAGS) -Wall -Wno-unused-function -I$(LCMS)/include dtref.c $(BUILD)/liblcms2.a -lm -o $@

$(BUILD)/dctl_gen.c: dctl2c.py ../AgX_darktable.dctl
	python3 dctl2c.py ../AgX_darktable.dctl $@

$(BUILD)/dctl_run: dctl_run.c dctl_shim.h $(BUILD)/dctl_gen.c
	$(CC) $(CFLAGS) -Wall -Wextra -Wno-unused-function -Wno-unused-parameter -I. dctl_run.c -lm -o $@

# el mismo DCTL con funciones matematicas que se equivocan hasta 4 ulp, como en una GPU
$(BUILD)/dctl_run_gpusim: dctl_run.c dctl_shim.h $(BUILD)/dctl_gen.c
	$(CC) $(CFLAGS) -DAGX_NOISY_MATH=4 -Wall -Wextra -Wno-unused-function -Wno-unused-parameter -I. dctl_run.c -lm -o $@

clean:
	rm -rf $(BUILD)

.PHONY: all clean
