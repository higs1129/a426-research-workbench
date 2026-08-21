package com.higs.linkconsole;

import android.content.Context;
import android.content.pm.PackageManager;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.os.Build;

final class VpnModeDetector {
    private static final String TAILSCALE_PACKAGE = "com.tailscale.ipn";
    private static final String CLASH_PACKAGE = "com.github.metacubex.clash.meta";

    private VpnModeDetector() {}

    static NetworkSnapshot.Mode detect(Context context) {
        ConnectivityManager manager =
                (ConnectivityManager) context.getSystemService(Context.CONNECTIVITY_SERVICE);
        if (manager == null) {
            return NetworkSnapshot.Mode.UNKNOWN;
        }
        Network network = manager.getActiveNetwork();
        NetworkCapabilities capabilities = network == null ? null : manager.getNetworkCapabilities(network);
        if (capabilities == null || !capabilities.hasTransport(NetworkCapabilities.TRANSPORT_VPN)) {
            return NetworkSnapshot.Mode.NONE;
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            int ownerUid = capabilities.getOwnerUid();
            if (ownerUid >= 0) {
                PackageManager packageManager = context.getPackageManager();
                String[] packages = packageManager.getPackagesForUid(ownerUid);
                if (packages != null) {
                    for (String packageName : packages) {
                        if (TAILSCALE_PACKAGE.equals(packageName)) {
                            return NetworkSnapshot.Mode.TAILSCALE;
                        }
                        if (CLASH_PACKAGE.equals(packageName)) {
                            return NetworkSnapshot.Mode.CLASH;
                        }
                    }
                }
            }
        }

        NetworkSnapshot.Mode lastSelected = WidgetState.getLastSelected(context);
        if (lastSelected == NetworkSnapshot.Mode.TAILSCALE || lastSelected == NetworkSnapshot.Mode.CLASH) {
            return lastSelected;
        }
        return NetworkSnapshot.Mode.UNKNOWN;
    }
}
