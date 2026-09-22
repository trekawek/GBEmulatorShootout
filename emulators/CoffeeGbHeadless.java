import eu.rekawek.coffeegb.controller.state.StateImage;
import eu.rekawek.coffeegb.core.Gameboy;
import eu.rekawek.coffeegb.core.Gameboy.BootstrapMode;
import eu.rekawek.coffeegb.core.Gameboy.GameboyConfiguration;
import eu.rekawek.coffeegb.core.events.EventBusImpl;
import eu.rekawek.coffeegb.core.gpu.Display;
import eu.rekawek.coffeegb.core.hardware.HardwareProfileRegistry;
import eu.rekawek.coffeegb.core.serial.SerialEndpoint;

import java.awt.image.BufferedImage;
import java.io.BufferedReader;
import java.io.File;
import java.io.InputStreamReader;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.Base64;
import java.util.concurrent.atomic.AtomicReference;
import javax.imageio.ImageIO;

/**
 * Persistent, headless Coffee GB bridge used by the Python shootout harness.
 *
 * <p>Keeping one JVM alive avoids paying for JVM/Swing startup and JIT warmup for every ROM. Each
 * request still creates a fresh isolated emulator, so one test cannot leak state into the next.
 */
public final class CoffeeGbHeadless {

    private CoffeeGbHeadless() {
    }

    public static void main(String[] args) throws Exception {
        var input = new BufferedReader(
                new InputStreamReader(System.in, StandardCharsets.UTF_8));
        var output = new PrintWriter(System.out, true, StandardCharsets.UTF_8);
        output.println("READY");

        String line;
        while ((line = input.readLine()) != null) {
            if (line.equals("QUIT")) {
                return;
            }
            handle(line, output);
        }
    }

    private static void handle(String line, PrintWriter output) {
        String[] fields = line.split("\\t", -1);
        String requestId = fields.length == 0 ? "?" : fields[0];
        try {
            if (fields.length != 5) {
                throw new IllegalArgumentException("Expected five request fields");
            }
            File rom = new File(decode(fields[1]));
            String profile = fields[2];
            long frames = Long.parseLong(fields[3]);
            Path screenshot = Path.of(decode(fields[4]));

            var configuration =
                    new GameboyConfiguration(rom)
                            .setHardwareProfile(HardwareProfileRegistry.resolve(profile))
                            .setBootstrapMode(BootstrapMode.FAST_FORWARD)
                            .setDisplaySgbBorder(false)
                            .setSupportBatterySave(false);
            writeFrame(run(configuration, frames), screenshot.toFile());
            output.println("OK\t" + requestId);
        } catch (Throwable failure) {
            failure.printStackTrace(System.err);
            String message = failure.getClass().getSimpleName() + ": " + failure.getMessage();
            output.println("ERROR\t" + requestId + "\t" + encode(message));
        }
    }

    private static StateImage run(GameboyConfiguration configuration, long frames) throws Exception {
        var latestFrame = new AtomicReference<StateImage>();
        var eventBus = new EventBusImpl(null, "shootout", false);
        eventBus.register(
                (Display.DmgFrameReadyEvent event) -> {
                    int[] rgb = new int[Display.DISPLAY_WIDTH * Display.DISPLAY_HEIGHT];
                    event.toRgb(rgb, false);
                    latestFrame.set(new StateImage(Display.DISPLAY_WIDTH, Display.DISPLAY_HEIGHT, rgb));
                },
                Display.DmgFrameReadyEvent.class);
        eventBus.register(
                (Display.GbcFrameReadyEvent event) -> {
                    int[] rgb = new int[Display.DISPLAY_WIDTH * Display.DISPLAY_HEIGHT];
                    event.toRgb(rgb, false);
                    latestFrame.set(new StateImage(Display.DISPLAY_WIDTH, Display.DISPLAY_HEIGHT, rgb));
                },
                Display.GbcFrameReadyEvent.class);

        Gameboy gameboy = null;
        try {
            gameboy = configuration.build();
            gameboy.init(eventBus, SerialEndpoint.NULL_ENDPOINT, null);
            long ticks = Math.multiplyExact(frames, configuration.getClockSpec().controllerTicksPerFrame());
            gameboy.runTicks(ticks);
            return latestFrame.get();
        } finally {
            if (gameboy != null) {
                gameboy.closeSilently();
            }
            eventBus.close();
        }
    }

    private static void writeFrame(StateImage image, File destination) throws Exception {
        if (image == null) {
            throw new IllegalStateException("Coffee GB produced no video frame");
        }
        int width = image.getWidth();
        int height = image.getHeight();
        int[] rgb = image.copyRgb();
        var buffered = new BufferedImage(width, height, BufferedImage.TYPE_INT_RGB);
        buffered.setRGB(0, 0, width, height, rgb, 0, width);
        if (!ImageIO.write(buffered, "png", destination)) {
            throw new IllegalStateException("No PNG writer is available");
        }
    }

    private static String decode(String value) {
        return new String(Base64.getUrlDecoder().decode(value), StandardCharsets.UTF_8);
    }

    private static String encode(String value) {
        return Base64.getUrlEncoder().withoutPadding()
                .encodeToString(value.getBytes(StandardCharsets.UTF_8));
    }
}
