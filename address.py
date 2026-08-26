"""列出当前 VISA 资源。只做环境检查，不打开仪器。"""

import pyvisa


def main():
    resource_manager = pyvisa.ResourceManager()
    try:
        resources = resource_manager.list_resources()
        print("VISA backend:", resource_manager.visalib)
        if resources:
            print("发现的 VISA 资源：")
            for resource in resources:
                print(" ", resource)
        else:
            print("未发现 VISA 资源。请检查 NI-VISA/NI-488.2、连线和仪器地址。")
    finally:
        resource_manager.close()


if __name__ == "__main__":
    main()
